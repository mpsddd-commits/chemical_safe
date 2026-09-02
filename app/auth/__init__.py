"""u5 authentication - C51 hashing, C52 tokens, C55 ownership.

Nothing here knows about uploads, and nothing in `app/uploads/` knows about
users. Keeping them apart is what lets the upload validator be tested without
inventing an account, and the hasher be tested without a database.
"""
