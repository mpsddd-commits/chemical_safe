"""u5 uploads - C53 validation, C54 storage.

Neither module knows who is uploading. That is deliberate: the validator's
question is "is this a PDF we can safely index?", which has nothing to do with
accounts, and keeping it that way is what lets it be tested without inventing a
user. Ownership is the service's business.
"""
