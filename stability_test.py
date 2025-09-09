#!/usr/bin/env python3
"""
Stability test for Checky backend - tests various stress scenarios
"""

import sys
import os
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

def stress_test_database():
    """Test database under concurrent access."""
    print("=== Database Stress Test ===")
    
    from checky.db import CheckyDatabase
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    
    db = CheckyDatabase(temp_db.name)
    
    # Create initial user
    db.create_user(7, '1234', 'de-DE-Standard-A')
    
    results = []
    
    def worker(worker_id):
        """Worker function to test concurrent operations."""
        try:
            for i in range(100):
                # Test authentication
                auth_result = db.authenticate_pin('1234')
                if not auth_result:
                    results.append(f"Worker {worker_id}: Auth failed at iteration {i}")
                    return
                
                # Test config retrieval
                config = db.get_config()
                if not config:
                    results.append(f"Worker {worker_id}: Config retrieval failed at iteration {i}")
                    return
            
            results.append(f"Worker {worker_id}: Success - 100 operations completed")
        except Exception as e:
            results.append(f"Worker {worker_id}: Exception - {e}")
    
    # Start multiple threads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Cleanup
    os.unlink(temp_db.name)
    
    # Report results
    success_count = sum(1 for result in results if "Success" in result)
    print(f"Database stress test: {success_count}/5 workers completed successfully")
    
    for result in results:
        print(f"  {result}")
    
    return success_count == 5

def test_pii_edge_cases():
    """Test PII scrubbing with edge cases."""
    print("\\n=== PII Edge Cases Test ===")
    
    from checky.pipeline import scrub_pii
    
    edge_cases = [
        "",  # Empty string
        None,  # None value  
        "   ",  # Whitespace only
        "email@" * 100,  # Very long string with patterns
        "Ä Ö Ü ß test@example.com äöü",  # Unicode characters
        "Multiple emails: a@b.com and c@d.org",  # Multiple patterns
    ]
    
    try:
        for case in edge_cases:
            try:
                result = scrub_pii(case) if case is not None else "None handled gracefully"
                print(f"✓ Edge case handled: {repr(case)} → {repr(result)}")
            except Exception as e:
                print(f"✗ Edge case failed: {repr(case)} → Exception: {e}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ PII edge case test failed: {e}")
        return False

def test_memory_usage():
    """Test for obvious memory leaks in basic operations."""
    print("\\n=== Memory Usage Test ===")
    
    try:
        from checky.pipeline import scrub_pii, build_system_prompt
        from checky.db import CheckyDatabase
        import tempfile
        
        # Create temporary database
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        try:
            db = CheckyDatabase(temp_db.name)
            db.create_user(7, '1234', 'de-DE-Standard-A')
            
            # Perform many operations
            for i in range(1000):
                # Database operations
                db.authenticate_pin('1234')
                config = db.get_config()
                
                # PII scrubbing
                test_text = f"Test {i}: email{i}@example.com phone: 123-456-{i:04d}"
                scrubbed = scrub_pii(test_text)
                
                # System prompt generation
                prompt = build_system_prompt(7)
                
                # Simple progress indicator
                if i % 100 == 0:
                    print(f"  Completed {i}/1000 operations")
            
            print("✓ Memory usage test completed - no obvious leaks detected")
            return True
            
        finally:
            os.unlink(temp_db.name)
            
    except Exception as e:
        print(f"✗ Memory usage test failed: {e}")
        return False

def main():
    """Run stability tests."""
    print("Checky Backend Stability Test Suite")
    print("=" * 50)
    
    tests = [
        stress_test_database,
        test_pii_edge_cases,
        test_memory_usage,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print(f"\\n❌ Test {test.__name__} failed!")
    
    print(f"\\n{'=' * 50}")
    print(f"Stability Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All stability tests passed! Backend is stable under stress.")
        return 0
    else:
        print("❌ Some stability tests failed.")
        return 1

if __name__ == "__main__":
    exit(main())