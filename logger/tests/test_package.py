import unittest


class PackageImportTest(unittest.TestCase):
    def test_package_imports(self):
        import logger

        self.assertTrue(hasattr(logger, 'log'))
        self.assertTrue(hasattr(logger, 'Logger'))

    def test_exposes_better_stack_setter(self):
        import logger

        self.assertTrue(hasattr(logger.log, 'set_better_stack'))

    def test_python2_module_is_gone(self):
        import importlib

        with self.assertRaises(ImportError):
            importlib.import_module('logger.loggly2')
