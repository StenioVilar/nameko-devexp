from os import name
from fastapi import APIRouter, status, HTTPException
from fastapi.params import Depends
from typing import List
from gateapi.api import schemas
from gateapi.api.dependencies import get_rpc, config
from .exceptions import OrderNotFound

from functools import lru_cache

router = APIRouter(
    prefix = "/orders",
    tags = ['Orders']
)

@router.get("/{order_id}", status_code=status.HTTP_200_OK)
def get_order(order_id: int, rpc = Depends(get_rpc)):
    try:
        return _get_order(order_id, rpc)
    except OrderNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        )

@lru_cache(maxsize=None)
def _get_order(order_id, nameko_rpc):
    # Retrieve order data from the orders service.
    # Note - this may raise a remote exception that has been mapped to
    # raise``OrderNotFound``
    with nameko_rpc.next() as nameko:
        order = nameko.orders.get_order(order_id)

    # Enhance order details with product and image details
    for item in order['order_details']:
        product_id = item['product_id']
        item['product'] = nameko_rpc.products_rpc.get(product_id)
        item['image'] = '{}/{}.jpg'.format(config['PRODUCT_IMAGE_ROOT'], product_id)

    return order

@router.post("", status_code=status.HTTP_200_OK, response_model=schemas.CreateOrderSuccess)
def create_order(request: schemas.CreateOrder, rpc = Depends(get_rpc)):
    id_ =  _create_order(request.dict(), rpc)
    return {
        'id': id_
    }

def _create_order(order_data, nameko_rpc):
    # check order product ids are valid
    with nameko_rpc.next() as nameko:
        valid_product_ids = {prod['id'] for prod in nameko.products.list()}
        for item in order_data['order_details']:
            if item['product_id'] not in valid_product_ids:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Product with id {item['product_id']} not found"
            )
        # Call orders-service to create the order.
        result = nameko.orders.create_order(
            order_data['order_details']
        )
        return result['id']

@router.get("", status_code=status.HTTP_200_OK)
def list_orders(rpc=Depends(get_rpc)):
    """Retrieves a list of all orders."""
    try:
        return _list_orders(rpc)
    except OrderNotFound:
        raise HTTPException(status_code=404, detail="No orders found")


def _list_orders(nameko_rpc):
    with nameko_rpc.next() as nameko:
        orders = nameko.orders.list_orders()

    # Enhance order details with product and image details.
    for order in orders:
        for item in order['order_details']:
            product_id = item['product_id']

            # Retrieve product details from the products service
            product_details = nameko.products_rpc.get(product_id)
            item['product'] = product_details
            # Construct an image url.
            item['image'] = '{}/{}.jpg'.format(config['PRODUCT_IMAGE_ROOT'], product_id)

    return orders