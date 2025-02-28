import string

# Base-62 character set
BASE62_CHARS = string.digits + string.ascii_letters  # 0-9, A-Z, a-z
BASE = len(BASE62_CHARS)  # Base is 62

def encode_base62(number: int) -> str:
    """
    Encodes a number into a Base-62 string of a given maximum length.
    
    :param number: The integer to encode.
    """
    if number == 0:
        return 0

    base62 = []

    while number > 0:
        remainder = number % BASE
        base62.append(BASE62_CHARS[remainder])
        number //= BASE

    return ''.join(reversed(base62))

def decode_base62(encoded: str) -> int:
    """
    Decodes a Base-62 string back into an integer.
    
    :param encoded: The Base-62 encoded string.
    :return: The decoded integer.
    """
    number = 0
    for char in encoded:
        if char not in BASE62_CHARS:
            raise ValueError(f"Invalid character '{char}' in encoded string.")
        number = number * BASE + BASE62_CHARS.index(char)
    return number
