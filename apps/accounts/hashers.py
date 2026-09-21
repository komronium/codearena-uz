from django.contrib.auth.hashers import PBKDF2PasswordHasher


class PBKDF2Hasher300k(PBKDF2PasswordHasher):
    """Django's default 1M iterations costs ~1.1s on the VPS CPU; 30 students
    logging in at contest start queued for ~8s. 300k (~0.3s) still meets the
    2023 OWASP floor-ish for a classroom site. Same algorithm name, so old
    hashes verify and get re-hashed on next login."""
    iterations = 300_000
