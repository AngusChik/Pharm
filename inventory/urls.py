from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from app.views import (
   InventoryView, EditProductView, AddProductView, CheckinProductView,
   LowStockView, CreateOrderView, OrderView, SubmitOrderView, delete_item,
   delete_order_item, ItemListView, DeleteRecentlyPurchasedProductView,
   DeleteAllOrdersView, DeleteAllRecentlyPurchasedView, signup, CustomLoginView, delete_one,
   UpdateOrderItemView, AddQuantityView
)


urlpatterns = [
   # Admin Site
   path('admin/', admin.site.urls),

   # Authentication
   path('login/', CustomLoginView.as_view(template_name='login.html'), name='login'),
   path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
   
   path('signup/', signup, name='signup'),

   # Default route
   path('', CustomLoginView.as_view(template_name='login.html'), name='home'),


   # Orders
   path('order/update-item/<int:item_id>/', UpdateOrderItemView.as_view(), name='update_order_item'),
   path('order/', CreateOrderView.as_view(), name='create_order'),
   path('order/submit/', SubmitOrderView.as_view(), name='submit_order'),
   path('orders/', OrderView.as_view(), name='order_view'),

   # Inventory
   path('inventory/', InventoryView.as_view(), name='inventory_display'),
   path('product/edit/<int:product_id>/', EditProductView.as_view(), name='edit_product'),
   path('new-product/', AddProductView.as_view(), name='new_product'),
   path('product/delete/<int:product_id>/', delete_item, name='delete_item'),

   # Low Stock
   path('low-stock/', LowStockView.as_view(), name='low_stock'),
   path('low-stock/delete/<int:id>/', DeleteRecentlyPurchasedProductView.as_view(), name='delete_recently_purchased_product'),
   path('low-stock/delete_all/', DeleteAllRecentlyPurchasedView.as_view(), name='delete_all_recently_purchased'),


   # Check-in
   path('checkin/', CheckinProductView.as_view(), name='checkin'),
   path('product/add-quantity/<int:product_id>/', AddQuantityView.as_view(), name='add_quantity'),
   path('delete_one/<int:product_id>/', delete_one, name='delete_one'),



   # Order Item Management
   path('order/delete-item/<int:item_id>/', delete_order_item, name='delete_order_item'),
   path('delete-orders/', DeleteAllOrdersView.as_view(), name='delete_all_orders'),


   # Item List
   path('item_list/', ItemListView.as_view(), name='item_list'),
]





