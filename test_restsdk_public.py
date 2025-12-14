import unittest
from unittest.mock import patch
from io import StringIO
import restsdk_public
from restsdk_public import findNextParent, hasAnotherParent, findTree
class TestHelper(unittest.TestCase):
   
    def test_find_next_parent(self):
        restsdk_public.fileDIC = {
            'file1': {'Parent': 'parent1'},
            'file2': {'Parent': 'parent2'},
            'file3': {'Parent': 'parent3'}
        }

        # Test when the fileID exists in the dictionary
        result = findNextParent('file2')
        self.assertEqual(result, 'parent2')

        # Test when the fileID does not exist in the dictionary
        result = findNextParent('file4')
        self.assertIsNone(result)

    def test_has_another_parent(self):
        restsdk_public.fileDIC = {
            'file1': {'Parent': 'parent1'},
            'file2': {'Parent': 'parent2'},
            'file3': {'Parent': None}
        }

        # Test when the fileID has another parent
        result = hasAnotherParent('file1')
        self.assertTrue(result)

        # Test when the fileID does not have another parent
        result = hasAnotherParent('file3')
        self.assertFalse(result)
   
    def test_find_tree_path(self):
        restsdk_public.fileDIC = {
            1: {'Name': 'parent', 'Parent': None, 'contentID': None},
            2: {'Name': 'child', 'Parent': 1, 'contentID': None},
        }
        path = findTree(2, 'file.txt', 1)
        self.assertEqual(path, 'parent/file.txt')
   
if __name__ == '__main__':
    unittest.main()
