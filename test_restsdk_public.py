import unittest
from unittest.mock import patch
from io import StringIO
from restsdk_public import findNextParent, hasAnotherParent, findTree
class TestHelper(unittest.TestCase):
   
    def test_find_next_parent(self):
        fileDIC = {
            'file1': {'Parent': 'parent1'},
            'file2': {'Parent': 'parent2'},
            'file3': {'Parent': 'parent3'}
        }

        # Test when the fileID exists in the dictionary
        result = findNextParent('file2', fileDIC)
        self.assertEqual(result, 'parent2')

        # Test when the fileID does not exist in the dictionary
        result = findNextParent('file4', fileDIC)
        self.assertIsNone(result)

    def test_has_another_parent(self):
        fileDIC = {
            'file1': {'Parent': 'parent1'},
            'file2': {'Parent': 'parent2'},
            'file3': {'Parent': None}
        }

        # Test when the fileID has another parent
        result = hasAnotherParent('file1', fileDIC)
        self.assertTrue(result)

        # Test when the fileID does not have another parent
        result = hasAnotherParent('file3', fileDIC)
        self.assertFalse(result)
   
if __name__ == '__main__':
    unittest.main()