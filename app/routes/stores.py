# app/routes/stores.py

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database.stores import add_store, get_all_stores, get_store_by_id
from app.routes.auth import get_current_user
from app.database.connection import get_connection

router = APIRouter()

class StoreCreate(BaseModel):
    name: str
    store_name: str = None
    location: str
    status: str = None

    def __init__(self, **data):
        super().__init__(**data)
        # Use name as store_name if store_name is not provided
        if self.store_name is None:
            self.store_name = self.name

class StoreResponse(BaseModel):
    store_id: int
    store_name: str
    location: str
    status: str = "active"
    createdAt: str = datetime.now().isoformat()

@router.post("/stores", response_model=StoreResponse)
def create_new_store(store_data: StoreCreate, current_user: dict = Depends(get_current_user)):
    """
    Creates a new store in the DB using app.database.stores.add_store.
    Returns a dict containing the newly created store_id and store_name.
    """
    try:
        new_id = add_store(store_data.store_name, store_data.location)
        return StoreResponse(
            store_id=new_id, 
            store_name=store_data.store_name,
            location=store_data.location,
            status="active",
            createdAt=datetime.now().isoformat()
        )
    except Exception as e:
        # For example, if there's a UNIQUE constraint on store_name
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/stores", response_model=List[StoreResponse])
def list_stores(current_user: dict = Depends(get_current_user)):
    """
    Lists all stores from the 'stores' table via app.database.stores.get_all_stores.
    Returns a list of store objects with additional fields for frontend compatibility.
    """
    stores = get_all_stores()
    # Add extra fields for frontend compatibility
    for store in stores:
        store["status"] = "active"
        store["createdAt"] = datetime.now().isoformat()
    return stores

@router.get("/stores/{store_id}", response_model=StoreResponse)
def get_store(store_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get a specific store by ID.
    Returns store details or 404 if not found.
    """
    store = get_store_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store with ID {store_id} not found")
    
    # Add extra fields for frontend compatibility
    store["status"] = "active"
    store["createdAt"] = datetime.now().isoformat()
    return store

@router.delete("/stores/{store_id}")
def delete_store(store_id: int, current_user: dict = Depends(get_current_user)):
    """
    Delete a store and all its associated cameras.
    """
    # First check if store exists
    store = get_store_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store with ID {store_id} not found")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # First delete all cameras associated with this store
    cursor.execute('DELETE FROM cameras WHERE store_id = ?', (store_id,))
    
    # Then delete the store
    cursor.execute('DELETE FROM stores WHERE store_id = ?', (store_id,))
    
    conn.commit()
    conn.close()
    
    return {"message": f"Store {store_id} and all its cameras deleted successfully"}
