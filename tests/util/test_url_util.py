from core.util import url_util


class TestUrlUtil:

    def test_encode_url_with_special_characters(self):
        url = "https://example.com/path with spaces/file?param=value&special=!@#$%^"
        result = url_util.encode_url(url=url)
        assert result == "https%3A//example.com/path%20with%20spaces/file%3Fparam%3Dvalue%26special%3D%21%40%23%24%25%5E"

    def test_encode_url_with_unicode_characters(self):
        url = "https://example.com/üñîçødé/文字"
        result = url_util.encode_url(url=url)
        assert result == "https%3A//example.com/%C3%BC%C3%B1%C3%AE%C3%A7%C3%B8d%C3%A9/%E6%96%87%E5%AD%97"

    def test_encode_url_with_safe_characters(self):
        url = "https://example.com/normal-path/file.txt"
        result = url_util.encode_url(url=url)
        assert result == "https%3A//example.com/normal-path/file.txt"

    def test_encode_url_part_with_special_characters(self):
        url_part = "file name with spaces!@#$%^&*()"
        result = url_util.encode_url_part(urlPart=url_part)
        assert result == "file%20name%20with%20spaces%21%40%23%24%25%5E%26%2A%28%29"

    def test_encode_url_part_with_unicode_characters(self):
        url_part = "üñîçødé文字"
        result = url_util.encode_url_part(urlPart=url_part)
        assert result == "%C3%BC%C3%B1%C3%AE%C3%A7%C3%B8d%C3%A9%E6%96%87%E5%AD%97"

    def test_encode_url_part_with_slashes(self):
        url_part = "path/to/file"
        result = url_util.encode_url_part(urlPart=url_part)
        assert result == "path%2Fto%2Ffile"

    def test_decode_url_with_encoded_special_characters(self):
        encoded_url = "https%3A//example.com/path%20with%20spaces/file%3Fparam%3Dvalue%26special%3D%21%40%23%24%25%5E"
        result = url_util.decode_url(url=encoded_url)
        assert result == "https://example.com/path with spaces/file?param=value&special=!@#$%^"

    def test_decode_url_with_encoded_unicode_characters(self):
        encoded_url = "https%3A//example.com/%C3%BC%C3%B1%C3%AE%C3%A7%C3%B8d%C3%A9/%E6%96%87%E5%AD%97"
        result = url_util.decode_url(url=encoded_url)
        assert result == "https://example.com/üñîçødé/文字"

    def test_decode_url_with_no_encoding(self):
        url = "https://example.com/normal-path/file.txt"
        result = url_util.decode_url(url=url)
        assert result == url

    def test_decode_url_part_with_encoded_special_characters(self):
        encoded_part = "file%20name%20with%20spaces%21%40%23%24%25%5E%26%2A%28%29"
        result = url_util.decode_url_part(urlPart=encoded_part)
        assert result == "file name with spaces!@#$%^&*()"

    def test_decode_url_part_with_encoded_unicode_characters(self):
        encoded_part = "%C3%BC%C3%B1%C3%AE%C3%A7%C3%B8d%C3%A9%E6%96%87%E5%AD%97"
        result = url_util.decode_url_part(urlPart=encoded_part)
        assert result == "üñîçødé文字"

    def test_decode_url_part_with_encoded_slashes(self):
        encoded_part = "path%2Fto%2Ffile"
        result = url_util.decode_url_part(urlPart=encoded_part)
        assert result == "path/to/file"

    def test_encode_decode_url_roundtrip(self):
        original_url = "https://example.com/path with spaces/üñîçødé/file?param=value&special=!@#$%^"
        encoded = url_util.encode_url(url=original_url)
        decoded = url_util.decode_url(url=encoded)
        assert decoded == original_url

    def test_encode_decode_url_part_roundtrip(self):
        original_part = "path/to/file with spaces and üñîçødé!@#$%^"
        encoded = url_util.encode_url_part(urlPart=original_part)
        decoded = url_util.decode_url_part(urlPart=encoded)
        assert decoded == original_part
