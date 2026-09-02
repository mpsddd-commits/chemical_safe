-- pgvector must exist before 0001_base creates the embedding column (DD-15).
CREATE EXTENSION IF NOT EXISTS vector;
