#!/usr/bin/env python3
"""
Test script to debug boolean processing issue
"""

def test_boolean_processing():
    """Test the boolean processing logic"""
    
    # Test the exact values from your error
    test_values = [
        '"[True]"',  # This is the problematic value
        '"[False]"',
        '"true"',
        '"false"',
        'true',
        'false',
        '[True]',
        '[False]',
        '["true"]',
        '["false"]',
    ]
    
    print("🔍 Testing boolean processing logic...")
    
    for value in test_values:
        print(f"\n📝 Testing value: {repr(value)} (type: {type(value).__name__})")
        
        try:
            if isinstance(value, str):
                # Handle various string formats
                clean_value = value.strip().lower()
                if clean_value in ['true', '1', 'yes', 'on']:
                    result = True
                    print(f"✅ Direct match: {result}")
                elif clean_value in ['false', '0', 'no', 'off']:
                    result = False
                    print(f"✅ Direct match: {result}")
                else:
                    # Try to evaluate string representations like "[True]"
                    try:
                        import ast
                        evaluated = ast.literal_eval(value)
                        if isinstance(evaluated, bool):
                            result = evaluated
                            print(f"✅ ast.literal_eval bool: {result}")
                        elif isinstance(evaluated, (list, tuple)) and len(evaluated) == 1:
                            result = bool(evaluated[0])
                            print(f"✅ ast.literal_eval list: {result}")
                        else:
                            result = bool(evaluated)
                            print(f"✅ ast.literal_eval other: {result}")
                    except (ValueError, SyntaxError) as e:
                        # If all else fails, default to False
                        result = False
                        print(f"❌ ast.literal_eval failed: {e} -> {result}")
            elif isinstance(value, (list, tuple)) and len(value) == 1:
                # Handle list/tuple with single value
                single_value = value[0]
                if isinstance(single_value, str):
                    result = single_value.lower() in ['true', '1', 'yes', 'on']
                else:
                    result = bool(single_value)
                print(f"✅ List/tuple: {result}")
            elif isinstance(value, bool):
                # Already a boolean, keep as is
                result = value
                print(f"✅ Already boolean: {result}")
            else:
                # Convert to boolean
                result = bool(value)
                print(f"✅ Converted: {result}")
                
        except Exception as e:
            print(f"❌ Error processing {repr(value)}: {e}")

if __name__ == "__main__":
    test_boolean_processing() 