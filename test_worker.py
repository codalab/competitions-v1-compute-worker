import tempfile
from unittest import TestCase
from worker import _clean_file


class TestWorkerUtils(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file = "{}/test.txt".format(self.temp_dir.name)
        self.suppressed_messages = [
            "WARNING: Your kernel does not support swap limit capabilities or the cgroup is not mounted. Memory limited without swap\n"
        ]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_file_simple(self):
        test_file = open(self.test_file, 'w')
        test_file.write('WARNING: Your kernel does not support swap limit capabilities or the cgroup is not mounted. Memory limited without swap.\n')
        test_file.write("This shouldn't trigger it\n")
        test_file.write("This shouldn't either\n")
        test_file.close()
        _clean_file(self.test_file)
        _clean_file(self.test_file)
        _clean_file(self.test_file)
        _clean_file(self.test_file)
        test_file = open(self.test_file, 'r')
        lines = test_file.readlines()
        for message in self.suppressed_messages:
            assert message not in lines
        assert "This shouldn't trigger it\n" in lines
        assert "This shouldn't either\n" in lines
        test_file.close()
