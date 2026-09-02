"""u4-evaluation - golden-set quality measurement (FR-36~39).

The unit exists to make quality a number that moves, and the shape of it is
decided by one measured fact: an answered query costs **5.25 LLM calls**
(`llm_call` census, 15 answered queries) against a free-tier cap of 20 per model
per day. A 25-question run is 131 calls - seven days.

So the work splits along whether a metric needs the model at all. Recall@k, MRR
and refusal accuracy are decided before generation and cost nothing; they run
every day over the whole set in seconds. Everything downstream of an answer runs
rarely, and has to survive being interrupted.
"""
