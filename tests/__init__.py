"""Project test package.

Keeping the repository tests as an explicit package makes ``unittest discover``
resolve ``tests.*`` helper imports from this checkout rather than an unrelated
third-party package installed in the interpreter.
"""
