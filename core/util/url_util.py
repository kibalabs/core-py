from urllib import parse


def encode_url(url: str) -> str:
    return parse.quote(string=url)


def encode_url_part(urlPart: str) -> str:
    return parse.quote(string=urlPart, safe='')


def decode_url(url: str) -> str:
    return parse.unquote(string=url)


def decode_url_part(urlPart: str) -> str:
    return parse.unquote(string=urlPart)
