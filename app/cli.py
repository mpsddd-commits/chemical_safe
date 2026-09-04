"""C60 CLI entry point.

Runs the same service methods the web routes use (DD-12), synchronously and
without a queue. That matters for two reasons: an operator can index without
Redis running, and a failing run is easy to reproduce in the foreground.

`evaluate` arrives with u4 and will exit non-zero on a quality regression
(NFR-26, UD-10).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime

from app.core.config import get_settings
from app.core.errors import ConfigurationError
from app.core.logging import bind, configure, get_logger
from app.db.engine import init_engine, session_scope

log = get_logger(__name__)


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise SystemExit(f"--since must be YYYY-MM-DD, got {value!r}") from None
    if parsed > datetime.now(UTC).date():
        raise SystemExit("--since cannot be in the future")
    return datetime.combine(parsed, datetime.min.time(), tzinfo=UTC)


def cmd_sources(_args: argparse.Namespace) -> int:
    from app.services.ingestion_service import IngestionService

    with session_scope() as session:
        service = IngestionService(session)
        service.sync_source_catalog()
        rows = service.list_sources()

    width = max((len(r["source_id"]) for r in rows), default=10)
    for row in rows:
        key_state = (
            "-"
            if not row["requires_api_key"]
            else ("ok" if row["api_key_configured"] else f"MISSING:{row['api_key_env']}")
        )
        print(
            f"{row['source_id']:<{width}}  {row['doc_type']:<9} "
            f"policy={row['policy_status']:<8} key={key_state}"
        )
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from app.services.ingestion_service import IngestionService

    since = _parse_since(args.since)
    with session_scope() as session:
        service = IngestionService(session)
        service.sync_source_catalog()
        result = service.start(args.source, since)

    if not result.accepted or result.job_id is None:
        print(f"거부됨: {result.reason}", file=sys.stderr)
        return 2

    bind(f"job-{result.job_id}")
    print(f"job {result.job_id} 시작")

    # Run inline rather than enqueueing: the CLI is the no-queue path.
    with session_scope() as session:
        outcome = IngestionService(session).execute(
            result.job_id, args.source, since.isoformat() if since else None
        )
    print(
        f"job {result.job_id} {outcome.get('status')} — "
        f"성공 {outcome.get('succeeded', 0)} / "
        f"건너뜀 {outcome.get('skipped', 0)} / "
        f"실패 {outcome.get('failed', 0)}"
    )
    if outcome.get("failures_by_kind"):
        for kind, count in outcome["failures_by_kind"].items():
            print(f"  {kind}: {count}")
    # partial is a success for exit-code purposes: some documents were indexed.
    return 0 if outcome.get("status") in {"succeeded", "partial"} else 1


def cmd_reindex(args: argparse.Namespace) -> int:
    from app.core.types import JobKind
    from app.db.repositories.jobs import JobRepo
    from app.jobs.tracker import JobTracker
    from app.services.indexing_service import IndexingService

    with session_scope() as session:
        job_id = JobTracker(JobRepo(session)).create(JobKind.REINDEX, {"scope": args.scope})

    bind(f"job-{job_id}")
    with session_scope() as session:
        outcome = IndexingService(session).reindex_job(job_id, args.scope)
    print(
        f"reindex {job_id} {outcome['status']} — "
        f"성공 {outcome['succeeded']} / 실패 {outcome['failed']}"
    )
    return 0 if outcome["status"] in {"succeeded", "partial"} else 1


def cmd_retype(args: argparse.Namespace) -> int:
    """Reconcile document.doc_type with config/sources.yaml, then re-index.

    Repeatable on purpose. `doc_type` was split into `substance` and `msds` on
    2026-08-30; the next spec change should be a command away, not a migration.
    """
    from app.services.indexing_service import IndexingService

    with session_scope() as session:
        outcome = IndexingService(session).retype_documents(apply=args.apply)

    if not outcome["applied"]:
        print(f"소스 {outcome['checked']}종 확인 — 불일치 {outcome['drifted']}건")
        for row in outcome["documents"]:
            print(f"  문서 {row['document_id']:>4}  {row['from']} → {row['to']}")
        if outcome["drifted"]:
            print()
            print("적용하려면 --apply. 문서를 갱신한 뒤 해당 문서만 재색인합니다.")
        return 0

    print(
        f"불일치 {outcome['drifted']}건 → 재색인 성공 {outcome['reindexed']} / "
        f"실패 {outcome['failed']}"
    )
    return 0 if outcome["failed"] == 0 else 1


def cmd_stats(_args: argparse.Namespace) -> int:
    from app.core.build import build_id
    from app.services.indexing_service import IndexingService

    with session_scope() as session:
        stats = IndexingService(session).stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    # Which code is answering. Defect 58 was five hours of a stale container,
    # and `stats` was one of the commands run against it - it reported the
    # corpus correctly and had no way to say the code was not the current one.
    print(f"build: {build_id()}")
    return 0


def _set_role(email: str, role: str) -> int:
    """The whole of B3's bootstrap: registration makes accounts, this makes admins.

    Deliberately **not** "the first account becomes the admin". That rule needs
    no operator, which is its appeal and its defect: on an exposed instance the
    role goes to whoever registers first. Two explicit steps - register on the
    web form, then run this - cost one command and cannot be won by being fast.

    Case is not the operator's problem: `normalise_email` is the same function
    registration used, so `Bob@x.com` finds the row stored as `bob@x.com`
    (BR-132). Two normalisations that disagree would be the same bug as none.
    """
    from app.db.repositories.accounts import UserRepo, normalise_email

    address = normalise_email(email)
    with session_scope() as session:
        account = UserRepo(session).by_email(address)
        if account is None:
            # Non-zero, and it names the address as stored. An operator who
            # typed the wrong address otherwise sees a silent success and
            # believes an admin exists.
            print(f"그런 계정이 없습니다: {address}", file=sys.stderr)
            return 2
        before = account.role
        account.role = role
        session.flush()

    if before == role:
        print(f"{address} 는 이미 {role} 입니다 — 바뀐 것 없음")
    else:
        print(f"{address} {before} → {role}")
    return 0


def cmd_grant_admin(args: argparse.Namespace) -> int:
    from app.core.types import Role

    return _set_role(args.email, Role.ADMIN.value)


def cmd_revoke_admin(args: argparse.Namespace) -> int:
    from app.core.types import Role

    return _set_role(args.email, Role.USER.value)


# Exit codes (UD-10 / NFR-26). 4 is deliberately not 1: a run that stopped
# because the daily quota ran out has not found a quality problem, and treating
# it as failure would leave CI permanently red on the free tier.
EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_GOLDEN_SET_INVALID = 2
EXIT_RUN_FAILED = 3
EXIT_PARTIAL = 4


def cmd_evaluate(args: argparse.Namespace) -> int:
    from app.evaluation.golden_set import GoldenSetError
    from app.evaluation.reporter import render_comparison, render_metrics
    from app.evaluation.types import RunMode, RunStatus, Verdict
    from app.services.evaluation_service import EvaluationService

    service = EvaluationService()

    try:
        if args.list:
            from app.core.build import build_id

            current_build = build_id()
            for run in service.list_runs(args.limit):
                mark = " ★기준선" if run["is_baseline"] else ""
                # BR-129 makes promotion a human act, so the history a human
                # reads has to say which rows a test suite made and what each
                # row measured. Without both, picking a run means guessing.
                if run.get("note"):
                    mark += f" [{run['note']}]"
                retrieval = (run.get("metrics") or {}).get("retrieval") or {}
                scores = "".join(
                    f"  {label} {value:.3f}"
                    if isinstance(value, int | float)
                    else f"  {label}   --  "
                    for label, value in (
                        ("R@5", retrieval.get("recall_at_5")),
                        ("MRR", retrieval.get("mrr")),
                    )
                )
                # `현재` marks the runs the deployed code can still reproduce.
                # Runs 1-153 have no build id at all and say so rather than
                # borrowing today's.
                code = run.get("build_id")
                stamp = "코드 미기록" if code is None else code
                if code == current_build:
                    stamp += " 현재"
                print(
                    f"{run['id']:>4}  {run['mode']:<14} {run['status']:<10} "
                    f"문항 {run['questions']:>3}  LLM {run['llm_calls']:>4}{scores}"
                    f"  {stamp:<17}{mark}"
                )
            return EXIT_OK

        if args.promote is not None:
            service.promote_baseline(args.promote, accept_stale=args.accept_stale)
            print(f"실행 {args.promote} 을 기준선으로 승격했습니다.")
            if args.accept_stale:
                print("  --accept-stale 로 승격했습니다. 실행 note 에 기록됩니다.")
            return EXIT_OK

        if args.compare is not None:
            report = service.compare(args.compare, args.baseline)
            print(render_comparison(report))
            return EXIT_REGRESSION if report.verdict is Verdict.REGRESSION else EXIT_OK

        if args.resume is not None:
            summary = service.resume(args.resume)
        elif args.retrieval_only or args.full:
            mode = RunMode.RETRIEVAL_ONLY if args.retrieval_only else RunMode.FULL
            summary = service.run(mode=mode, golden_set_path=args.golden_set)
        else:
            print("실행 모드를 지정하세요:", file=sys.stderr)
            print(
                "  --retrieval-only  LLM 0 호출, 수초. 매일 돌릴 수 있습니다",
                file=sys.stderr,
            )
            print(
                "  --full            문항당 6.25 호출. 무료 티어에서 25문항이 7일입니다",
                file=sys.stderr,
            )
            return EXIT_RUN_FAILED
    except GoldenSetError as exc:
        # Before anything ran, by design (BR-114).
        print("골든셋 검증 실패:", file=sys.stderr)
        print(exc, file=sys.stderr)
        return EXIT_GOLDEN_SET_INVALID
    except ConfigurationError as exc:
        print(f"설정 오류: {exc}", file=sys.stderr)
        return EXIT_RUN_FAILED

    print(f"실행 {summary.run_id} — {summary.status.value}")
    print(render_metrics(summary.metrics))
    if summary.comparison is not None:
        print()
        print(render_comparison(summary.comparison))

    if summary.status is RunStatus.PARTIAL:
        print(
            "할당량으로 중단되었습니다. 이어서: "
            f"safeenv evaluate --resume {summary.run_id}",
            file=sys.stderr,
        )
        return EXIT_PARTIAL
    if summary.comparison is not None and summary.comparison.verdict is Verdict.REGRESSION:
        return EXIT_REGRESSION
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="safeenv", description="safeenv 관리 명령")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sources", help="소스 목록과 정책·인증키 상태").set_defaults(func=cmd_sources)

    ingest = sub.add_parser("ingest", help="소스 수집 실행 (동기)")
    ingest.add_argument("--source", required=True, help="source_id")
    ingest.add_argument("--since", help="YYYY-MM-DD 이후 변경분만")
    ingest.set_defaults(func=cmd_ingest)

    reindex = sub.add_parser("reindex", help="보관 원본으로 재색인")
    reindex.add_argument("--scope", default="all", choices=["all"])
    reindex.set_defaults(func=cmd_reindex)

    retype = sub.add_parser(
        "retype", help="문서 doc_type 을 config/sources.yaml 과 맞추고 재색인"
    )
    retype.add_argument(
        "--apply",
        action="store_true",
        help="실제로 적용한다. 없으면 무엇이 바뀔지만 보여준다",
    )
    retype.set_defaults(func=cmd_retype)

    sub.add_parser("stats", help="색인 현황").set_defaults(func=cmd_stats)

    grant = sub.add_parser("grant-admin", help="계정을 관리자로 승격 (B3)")
    grant.add_argument("email", help="가입한 이메일")
    grant.set_defaults(func=cmd_grant_admin)

    revoke = sub.add_parser("revoke-admin", help="관리자 권한 회수 (B3)")
    revoke.add_argument("email", help="가입한 이메일")
    revoke.set_defaults(func=cmd_revoke_admin)

    evaluate = sub.add_parser("evaluate", help="골든셋 품질 평가 (FR-36~39)")
    # Mutually exclusive and neither is a default. A bare `evaluate` must not be
    # able to start a run that costs a week of free-tier quota by accident - the
    # mode is a decision, so it is typed out.
    mode = evaluate.add_mutually_exclusive_group()
    mode.add_argument(
        "--retrieval-only",
        action="store_true",
        help="검색 지표만. LLM 을 호출하지 않는다 (BR-119) — 매일 돌릴 수 있다",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help="전체 지표. 문항당 6.25 호출 — 무료 티어에서 25문항이 7일",
    )
    evaluate.add_argument("--golden-set", help="골든셋 경로 (기본 GOLDEN_SET_PATH)")
    evaluate.add_argument("--resume", type=int, metavar="RUN_ID", help="중단된 실행 이어하기")
    evaluate.add_argument("--list", action="store_true", help="실행 이력")
    evaluate.add_argument("--limit", type=int, default=20, help="--list 개수")
    evaluate.add_argument("--compare", type=int, metavar="RUN_ID", help="기준선 대비 비교")
    evaluate.add_argument("--baseline", type=int, metavar="RUN_ID", help="비교 기준선 지정")
    evaluate.add_argument(
        "--promote", type=int, metavar="RUN_ID", help="기준선으로 승격 (BR-129)"
    )
    evaluate.add_argument(
        "--accept-stale",
        action="store_true",
        help="지금 도는 코드가 아닌 실행을 승격 (--full 은 측정에 이틀이 든다). 기록됨",
    )
    evaluate.set_defaults(func=cmd_evaluate)
    return parser


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    configure(settings.log_level, settings.log_dir)
    init_engine(settings)
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
