import unittest
import os
import json
import tempfile
import sys
import os

# Add the parent directory to the path to import from utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.auth import read_auth_config

class TestAuthConfig(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.test_config_path = os.path.join(self.test_dir, "auth.json")
    
    def tearDown(self):
        # Clean up the temporary directory
        if os.path.exists(self.test_dir):
            for file in os.listdir(self.test_dir):
                os.remove(os.path.join(self.test_dir, file))
            os.rmdir(self.test_dir)
    
    def test_read_auth_config_creates_default_file(self):
        """Test that read_auth_config creates a default config file when none exists"""
        config = read_auth_config(self.test_config_path)
        
        # Check that the config has the expected structure
        self.assertIn("mac", config)
        self.assertIn("key", config)
        self.assertIn("filepath", config)
        
        # Check that file was actually created
        self.assertTrue(os.path.exists(self.test_config_path))
        
        # Check that the created file has valid JSON
        with open(self.test_config_path, "r") as f:
            saved_config = json.load(f)
        self.assertEqual(config, saved_config)
    
    def test_read_auth_config_reads_existing_file(self):
        """Test that read_auth_config reads an existing config file correctly"""
        # Create a custom config file
        custom_config = {
            "mac": "00:11:22:33:44:55",
            "key": "test-key",
            "filepath": "/path/to/device/file"
        }
        
        # Write the custom config to the test file
        with open(self.test_config_path, "w") as f:
            json.dump(custom_config, f, indent=4)
        
        # Read the config using our function
        config = read_auth_config(self.test_config_path)
        
        # Verify the values match what we wrote
        self.assertEqual(config["mac"], "00:11:22:33:44:55")
        self.assertEqual(config["key"], "test-key")
        self.assertEqual(config["filepath"], "/path/to/device/file")

if __name__ == '__main__':
    unittest.main()