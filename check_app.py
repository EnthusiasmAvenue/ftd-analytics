#!/usr/bin/env python3
"""
Quick check to verify app.py can be imported and has 'app' attribute
Run this BEFORE deploying to Render
"""

import sys

def check_app():
    print("🔍 Checking if app.py can be loaded...")
    
    try:
        # Try importing the module
        import app as app_module
        print("✅ app.py imported successfully")
        
        # Check if 'app' attribute exists
        if hasattr(app_module, 'app'):
            print("✅ 'app' attribute found")
            print(f"   Type: {type(app_module.app)}")
            
            # Check if it's a FastAPI instance
            from fastapi import FastAPI
            if isinstance(app_module.app, FastAPI):
                print("✅ 'app' is a valid FastAPI instance")
                print("\n🚀 Your app is ready for Render deployment!")
                print("\nDeploy command:")
                print("   uvicorn app:app --host 0.0.0.0 --port $PORT")
                return True
            else:
                print("❌ 'app' is not a FastAPI instance")
                return False
        else:
            print("❌ 'app' attribute NOT found in module")
            print("\n📝 Available attributes:")
            for attr in dir(app_module):
                if not attr.startswith('_'):
                    print(f"   - {attr}")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import app.py: {e}")
        print("\n🔧 Make sure:")
        print("   1. app.py exists in current directory")
        print("   2. All dependencies installed: pip install -r requirements.txt")
        print("   3. No syntax errors in app.py")
        return False
        
    except Exception as e:
        print(f"❌ Error checking app: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = check_app()
    sys.exit(0 if success else 1)