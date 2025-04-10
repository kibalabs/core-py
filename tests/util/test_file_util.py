import os
import pathlib
import shutil
import tempfile
import time

import pytest

from core.util import file_util


class TestFileUtil:

    @pytest.fixture
    def temp_dir(self):
        temp_directory = tempfile.mkdtemp()
        yield temp_directory
        if os.path.exists(temp_directory):
            shutil.rmtree(temp_directory)

    @pytest.fixture
    def temp_file(self, temp_dir):
        temp_file_path = os.path.join(temp_dir, "test_file.txt")
        with open(temp_file_path, "w") as f:
            f.write("test content")
        yield temp_file_path
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    @pytest.fixture
    def nested_temp_dir(self, temp_dir):
        nested_dir = os.path.join(temp_dir, "nested", "directory")
        os.makedirs(nested_dir)
        yield nested_dir

    async def test_remove_file_removes_existing_file(self, temp_file):
        assert os.path.exists(temp_file)
        await file_util.remove_file(temp_file)
        assert not os.path.exists(temp_file)

    async def test_remove_file_ignores_missing_file_by_default(self):
        non_existent_file = "/tmp/non_existent_file.txt"
        await file_util.remove_file(non_existent_file)

    async def test_remove_file_raises_for_missing_file_when_configured(self):
        non_existent_file = "/tmp/non_existent_file.txt"
        with pytest.raises(FileNotFoundError):
            await file_util.remove_file(non_existent_file, should_ignore_missing=False)

    async def test_remove_directory_removes_existing_directory(self, temp_dir):
        test_dir = os.path.join(temp_dir, "test_dir")
        os.makedirs(test_dir)
        assert os.path.exists(test_dir)
        await file_util.remove_directory(test_dir)
        assert not os.path.exists(test_dir)

    async def test_remove_directory_ignores_missing_directory_by_default(self):
        non_existent_dir = "/tmp/non_existent_dir"
        await file_util.remove_directory(non_existent_dir)

    async def test_remove_directory_raises_for_missing_directory_when_configured(self):
        non_existent_dir = "/tmp/non_existent_dir"
        with pytest.raises(FileNotFoundError):
            await file_util.remove_directory(non_existent_dir, should_ignore_missing=False)

    def test_remove_file_sync_removes_existing_file(self, temp_file):
        assert os.path.exists(temp_file)
        file_util.remove_file_sync(temp_file)
        assert not os.path.exists(temp_file)

    def test_remove_file_sync_ignores_missing_file_by_default(self):
        non_existent_file = "/tmp/non_existent_file.txt"
        file_util.remove_file_sync(non_existent_file)

    def test_remove_file_sync_raises_for_missing_file_when_configured(self):
        non_existent_file = "/tmp/non_existent_file.txt"
        with pytest.raises(FileNotFoundError):
            file_util.remove_file_sync(non_existent_file, should_ignore_missing=False)

    def test_remove_directory_sync_removes_existing_directory(self, temp_dir):
        test_dir = os.path.join(temp_dir, "test_dir")
        os.makedirs(test_dir)
        assert os.path.exists(test_dir)
        file_util.remove_directory_sync(test_dir)
        assert not os.path.exists(test_dir)

    def test_remove_directory_sync_ignores_missing_directory_by_default(self):
        non_existent_dir = "/tmp/non_existent_dir"
        file_util.remove_directory_sync(non_existent_dir)

    def test_remove_directory_sync_raises_for_missing_directory_when_configured(self):
        non_existent_dir = "/tmp/non_existent_dir"
        with pytest.raises(FileNotFoundError):
            file_util.remove_directory_sync(non_existent_dir, should_ignore_missing=False)

    async def test_file_exists_returns_true_for_existing_file(self, temp_file):
        assert await file_util.file_exists(temp_file) is True

    async def test_file_exists_returns_false_for_nonexistent_file(self):
        non_existent_file = "/tmp/non_existent_file.txt"
        assert await file_util.file_exists(non_existent_file) is False

    def test_file_exists_sync_returns_true_for_existing_file(self, temp_file):
        assert file_util.file_exists_sync(temp_file) is True

    def test_file_exists_sync_returns_false_for_nonexistent_file(self):
        non_existent_file = "/tmp/non_existent_file.txt"
        assert file_util.file_exists_sync(non_existent_file) is False

    async def test_get_file_age_millis_returns_age_of_file(self, temp_file):
        created_time = os.path.getmtime(temp_file)
        time.sleep(0.1)  # Ensure some time passes
        age_millis = await file_util.get_file_age_millis(temp_file)
        assert age_millis >= 100  # At least 100ms should have passed

    def test_get_file_age_millis_sync_returns_age_of_file(self, temp_file):
        created_time = os.path.getmtime(temp_file)
        time.sleep(0.1)  # Ensure some time passes
        age_millis = file_util.get_file_age_millis_sync(temp_file)
        assert age_millis >= 100  # At least 100ms should have passed

    async def test_read_file_returns_file_contents(self, temp_file):
        content = await file_util.read_file(temp_file)
        assert content == "test content"

    async def test_read_file_bytes_returns_binary_contents(self, temp_file):
        content = await file_util.read_file_bytes(temp_file)
        assert content == b"test content"

    def test_read_file_sync_returns_file_contents(self, temp_file):
        content = file_util.read_file_sync(temp_file)
        assert content == "test content"

    def test_read_file_bytes_sync_returns_binary_contents(self, temp_file):
        content = file_util.read_file_bytes_sync(temp_file)
        assert content == b"test content"

    async def test_write_file_creates_file_with_content(self, temp_dir):
        test_file = os.path.join(temp_dir, "write_test.txt")
        await file_util.write_file(test_file, "new content")
        assert os.path.exists(test_file)
        with open(test_file, "r") as f:
            assert f.read() == "new content"

    async def test_write_file_creates_parent_directories(self, temp_dir):
        test_file = os.path.join(temp_dir, "nested", "dir", "write_test.txt")
        await file_util.write_file(test_file, "nested content")
        assert os.path.exists(test_file)
        with open(test_file, "r") as f:
            assert f.read() == "nested content"

    async def test_write_file_raises_when_file_exists_if_configured(self, temp_file):
        with pytest.raises(FileExistsError):
            await file_util.write_file(temp_file, "overwrite content", shouldRaiseIfFileExists=True)

    async def test_write_file_bytes_creates_file_with_binary_content(self, temp_dir):
        test_file = os.path.join(temp_dir, "write_binary_test.txt")
        binary_content = b"binary content"
        await file_util.write_file_bytes(test_file, binary_content)
        assert os.path.exists(test_file)
        with open(test_file, "rb") as f:
            assert f.read() == binary_content

    def test_write_file_sync_creates_file_with_content(self, temp_dir):
        test_file = os.path.join(temp_dir, "write_sync_test.txt")
        file_util.write_file_sync(test_file, "sync content")
        assert os.path.exists(test_file)
        with open(test_file, "r") as f:
            assert f.read() == "sync content"

    def test_write_file_sync_creates_parent_directories(self, temp_dir):
        test_file = os.path.join(temp_dir, "nested", "sync", "write_test.txt")
        file_util.write_file_sync(test_file, "nested sync content")
        assert os.path.exists(test_file)
        with open(test_file, "r") as f:
            assert f.read() == "nested sync content"

    def test_write_file_sync_raises_when_file_exists_if_configured(self, temp_file):
        with pytest.raises(FileExistsError):
            file_util.write_file_sync(temp_file, "overwrite content", shouldRaiseIfFileExists=True)

    def test_write_file_bytes_sync_creates_file_with_binary_content(self, temp_dir):
        test_file = os.path.join(temp_dir, "write_binary_sync_test.txt")
        binary_content = b"binary sync content"
        file_util.write_file_bytes_sync(test_file, binary_content)
        assert os.path.exists(test_file)
        with open(test_file, "rb") as f:
            assert f.read() == binary_content

    async def test_create_directory_creates_new_directory(self, temp_dir):
        new_dir = os.path.join(temp_dir, "new_directory")
        await file_util.create_directory(new_dir)
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

    async def test_create_directory_creates_nested_directories(self, temp_dir):
        nested_dir = os.path.join(temp_dir, "nested", "directory", "structure")
        await file_util.create_directory(nested_dir)
        assert os.path.exists(nested_dir)
        assert os.path.isdir(nested_dir)

    async def test_create_directory_allows_existing_by_default(self, nested_temp_dir):
        await file_util.create_directory(nested_temp_dir)
        assert os.path.exists(nested_temp_dir)

    async def test_create_directory_raises_when_existing_if_configured(self, nested_temp_dir):
        with pytest.raises(FileExistsError):
            await file_util.create_directory(nested_temp_dir, shouldAllowExisting=False)

    def test_create_directory_sync_creates_new_directory(self, temp_dir):
        new_dir = os.path.join(temp_dir, "new_directory_sync")
        file_util.create_directory_sync(new_dir)
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

    def test_create_directory_sync_creates_nested_directories(self, temp_dir):
        nested_dir = os.path.join(temp_dir, "nested", "directory", "structure_sync")
        file_util.create_directory_sync(nested_dir)
        assert os.path.exists(nested_dir)
        assert os.path.isdir(nested_dir)

    def test_create_directory_sync_allows_existing_by_default(self, nested_temp_dir):
        file_util.create_directory_sync(nested_temp_dir)
        assert os.path.exists(nested_temp_dir)

    def test_create_directory_sync_raises_when_existing_if_configured(self, nested_temp_dir):
        with pytest.raises(FileExistsError):
            file_util.create_directory_sync(nested_temp_dir, shouldAllowExisting=False)

    def test_get_file_extension_returns_correct_extension(self):
        assert file_util.get_file_extension("file.txt") == ".txt"
        assert file_util.get_file_extension("path/to/file.jpg") == ".jpg"
        assert file_util.get_file_extension("file.with.multiple.dots.pdf") == ".pdf"
        assert file_util.get_file_extension("file_without_extension") == ""
        assert file_util.get_file_extension(".hidden") == ""
