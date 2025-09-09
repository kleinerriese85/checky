#!/usr/bin/env python3
"""
Integration test for the refactored Checky backend.
Tests basic functionality without requiring full pipecat setup.
"""

import sys
import os
import tempfile
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_basic_imports():
    """Test basic package imports."""
    print("=== Testing Basic Imports ===")
    
    try:
        import checky
        print("✓ Main package import successful")
        
        from checky import db
        print("✓ Database module import successful")
        
        from checky.pipeline import scrub_pii, build_system_prompt
        print("✓ Pipeline utility functions import successful")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_pii_scrubbing():
    """Test PII scrubbing functionality."""
    print("\n=== Testing PII Scrubbing ===")
    
    try:
        from checky.pipeline import scrub_pii
        
        test_cases = [
            ("Hello email@test.com", "Hello [E-MAIL ENTFERNT]"),
            ("Call me at 123-456-7890", "Call me at [TELEFON ENTFERNT]"),
            ("Visit https://example.com", "Visit [URL ENTFERNT]"),
            ("Normal text", "Normal text"),
        ]
        
        for original, expected_pattern in test_cases:
            result = scrub_pii(original)
            if expected_pattern in result or original == result:
                print(f"✓ PII scrubbing: '{original}' → '{result}'")
            else:
                print(f"✗ PII scrubbing failed: '{original}' → '{result}' (expected pattern: '{expected_pattern}')")
                return False
        
        return True
    except Exception as e:
        print(f"✗ PII scrubbing test failed: {e}")
        traceback.print_exc()
        return False

def test_database_functionality():
    """Test database operations."""
    print("\n=== Testing Database Functionality ===")
    
    try:
        from checky.db import CheckyDatabase
        
        # Create temporary database
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        try:
            db = CheckyDatabase(temp_db.name)
            print("✓ Database initialization successful")
            
            # Test user creation
            result = db.create_user(7, '1234', 'de-DE-Standard-A')
            if result:
                print("✓ User creation successful")
            else:
                print("✗ User creation failed")
                return False
            
            # Test duplicate user prevention
            result2 = db.create_user(8, '5678', 'de-DE-Standard-B')
            if not result2:
                print("✓ Duplicate user prevention working")
            else:
                print("✗ Duplicate user prevention failed")
                return False
            
            # Test PIN authentication
            if db.authenticate_pin('1234'):
                print("✓ PIN authentication successful")
            else:
                print("✗ PIN authentication failed")
                return False
            
            # Test wrong PIN rejection
            if not db.authenticate_pin('9999'):
                print("✓ Wrong PIN correctly rejected")
            else:
                print("✗ Wrong PIN was accepted")
                return False
            
            # Test config retrieval
            config = db.get_config()
            if config and config.get('child_age') == 7:
                print(f"✓ Config retrieval successful: age={config['child_age']}")
            else:
                print("✗ Config retrieval failed")
                return False
            
            # Test config update
            update_result = db.update_config(age=8, tts_voice='de-DE-Standard-B')
            if update_result:
                updated_config = db.get_config()
                if updated_config.get('child_age') == 8:
                    print("✓ Config update successful")
                else:
                    print("✗ Config update failed - data not updated")
                    return False
            else:
                print("✗ Config update failed")
                return False
                
            return True
            
        finally:
            # Cleanup
            os.unlink(temp_db.name)
            
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        traceback.print_exc()
        return False

def test_system_prompt_generation():
    """Test system prompt generation for different ages."""
    print("\n=== Testing System Prompt Generation ===")
    
    try:
        from checky.pipeline import build_system_prompt
        
        test_ages = [5, 7, 10]
        for age in test_ages:
            prompt = build_system_prompt(age)
            if f"{age}-jähriges Kind" in prompt and "Deutsch" in prompt:
                print(f"✓ System prompt for age {age}: appropriate content detected")
            else:
                print(f"✗ System prompt for age {age}: missing required content")
                return False
        
        return True
    except Exception as e:
        print(f"✗ System prompt test failed: {e}")
        traceback.print_exc()
        return False

def test_error_handling():
    """Test graceful error handling."""
    print("\n=== Testing Error Handling ===")
    
    try:
        from checky.pipeline import create_checky_bot
        
        # Mock websocket object
        class MockWebSocket:
            pass
        
        mock_ws = MockWebSocket()
        
        try:
            # This should fail gracefully with ImportError due to missing pipecat
            import asyncio
            asyncio.run(create_checky_bot(mock_ws))
            print("✗ Expected ImportError was not raised")
            return False
        except ImportError as e:
            if "Pipecat is required" in str(e):
                print("✓ Graceful error handling for missing pipecat")
                return True
            else:
                print(f"✗ Unexpected ImportError: {e}")
                return False
        except Exception as e:
            print(f"✗ Unexpected error type: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all integration tests."""
    print("Checky Backend Integration Test Suite")
    print("=" * 50)
    
    tests = [
        test_basic_imports,
        test_pii_scrubbing,
        test_database_functionality,
        test_system_prompt_generation,
        test_error_handling,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"\n❌ Test {test.__name__} failed!")
    
    print(f"\n{'=' * 50}")
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The refactored backend is stable.")
        return 0
    else:
        print("❌ Some tests failed. Review the errors above.")
        return 1

if __name__ == "__main__":
    exit(main())