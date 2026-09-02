"""Retrieval, generation and citation (u2-rag-qa).

`app/rag/` is a *responsibility* boundary, not a unit boundary. Units are a
development-order concept and never a directory (UD-4): u3's substance card and
u5's uploads both retrieve and cite, and they will import from here.
"""
