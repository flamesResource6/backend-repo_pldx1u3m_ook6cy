import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from bson import ObjectId

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


# -------------------- Products API --------------------
class ProductIn(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in EUR")
    category: Optional[str] = Field(None, description="Product category")
    in_stock: bool = Field(True, description="In stock")
    image_urls: List[HttpUrl] = Field(default_factory=list)
    video_url: Optional[HttpUrl] = None

class ProductOut(ProductIn):
    id: str


@app.get("/api/products", response_model=List[ProductOut])
def list_products():
    from database import get_documents
    docs = get_documents("product", {}, limit=100)
    out: List[ProductOut] = []
    for d in docs:
        # Convert ObjectId to string if present
        _id = str(d.get("_id")) if d.get("_id") else ""
        # Remove Mongo internal fields
        d.pop("_id", None)
        d.pop("created_at", None)
        d.pop("updated_at", None)
        out.append(ProductOut(id=_id, **d))
    return out


@app.post("/api/products", response_model=dict)
def create_product(payload: ProductIn):
    from database import create_document
    product_id = create_document("product", payload)
    return {"id": product_id}


class CheckoutIn(BaseModel):
    product_id: str
    quantity: int = Field(1, ge=1, le=10)

class CheckoutOut(BaseModel):
    status: str
    message: str
    order_id: str


@app.post("/api/checkout", response_model=CheckoutOut)
def checkout(payload: CheckoutIn):
    # This is a mock checkout implementation for demo purposes.
    # In production, integrate with Stripe/PayPal and verify payment.
    try:
        # Basic validation that product exists
        from database import db
        if db is None:
            raise HTTPException(status_code=500, detail="Database not available")
        try:
            oid = ObjectId(payload.product_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product_id")
        product = db["product"].find_one({"_id": oid})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        # Create a simple order record
        order = {
            "product_id": payload.product_id,
            "quantity": payload.quantity,
            "status": "paid",  # mock status
        }
        res = db["order"].insert_one(order)
        return CheckoutOut(status="success", message="Payment processed (demo)", order_id=str(res.inserted_id))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
