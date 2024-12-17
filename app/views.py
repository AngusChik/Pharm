from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic.edit import FormView
from django.contrib import messages 
from django.db.models import Sum
from django.db.models import F
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.cache import cache
from app.mixins import AdminRequiredMixin
from django.contrib.auth.decorators import login_required #for @login_required 
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import UserPassesTestMixin
from datetime import datetime
from django.http import HttpResponseRedirect  # To handle redirection to the referrer
from django.db import IntegrityError  # To handle IntegrityError
import time
from .forms import  EditProductForm, OrderDetailForm, BarcodeForm, ItemForm, AddProductForm
from .models import Item, Product, Category, Order, OrderDetail, Customer, RecentlyPurchasedProduct


# Home view
@login_required
def home(request):
   if not request.user.is_authenticated:
       return redirect('login')  # Redirect to login page
   return render(request, 'home.html')


def signup(request):
   if request.method == 'POST':
       form = UserCreationForm(request.POST)
       if form.is_valid():
           form.save()
           messages.success(request, "Your account has been created successfully! You can now log in.")
           return redirect('login')
   else:
       form = UserCreationForm()
   return render(request, 'signup.html', {'form': form})
  
class CustomLoginView(LoginView):
    def get(self, request, *args, **kwargs):
        # Redirect authenticated users to the appropriate page
        if request.user.is_authenticated:
            if request.user.is_staff:  # Redirect admins
                return redirect('inventory_display')  # Example: Admin page
            return redirect('checkin')  # Example: Regular user page
        return super().get(request, *args, **kwargs)

    def get_success_url(self):
        """
        Redirect users based on their role after a successful login.
        """
        if self.request.user.is_staff:
            return reverse('inventory_display')  # Admin-specific page
        return reverse('checkin')  # Regular user page

# View to handle the creation of orders
class CreateOrderView(LoginRequiredMixin, View):
    template_name = 'order_form.html'

    def get_order(self, request):
        order_id = request.session.get('order_id')
        if order_id:
            try:
                order = Order.objects.get(order_id=order_id)
            except Order.DoesNotExist:
                order = self._create_new_order(request)
        else:
            order = self._create_new_order(request)
        return order

    def _create_new_order(self, request):
        last_order = Order.objects.order_by('-order_id').first()
        next_order_id = 1 if not last_order else last_order.order_id + 1
        order = Order.objects.create(order_id=next_order_id, total_price=Decimal('0.00'))
        request.session['order_id'] = order.order_id
        return order

    def get(self, request, *args, **kwargs):
        order = self.get_order(request)
        form = BarcodeForm()

        # Order details sorted in reverse (newest first)
        order_details = order.details.all().order_by('-order_date')  # Use '-id' if no `order_date` field exists
        total_price_before_tax = sum(detail.product.price * detail.quantity for detail in order_details)
        total_price_after_tax = total_price_before_tax * Decimal('1.13')

        return render(request, self.template_name, {
            'order': order,
            'form': form,
            'order_details': order_details,
            'total_price_before_tax': total_price_before_tax,
            'total_price_after_tax': total_price_after_tax,
        })

    def post(self, request, *args, **kwargs):
        order = self.get_order(request)
        form = BarcodeForm(request.POST)

        if form.is_valid():
            barcode = form.cleaned_data['barcode']
            quantity = form.cleaned_data.get('quantity', 1)

            try:
                product = Product.objects.get(barcode=barcode)
            except Product.DoesNotExist:
                messages.error(request, f"No product found with barcode '{barcode}'.")
                # Render the template with the current context and error message
                order_details = order.details.all().order_by('-order_date')  # Use '-id' if no order_date exists
                total_price_before_tax = sum(detail.product.price * detail.quantity for detail in order_details)
                total_price_after_tax = total_price_before_tax * Decimal('1.13')
                return render(request, self.template_name, {
                    'order': order,
                    'form': form,
                    'order_details': order_details,
                    'total_price_before_tax': total_price_before_tax,
                    'total_price_after_tax': total_price_after_tax,
                })

            if product.quantity_in_stock < quantity:
                messages.error(request, f"Not enough stock for {product.name}.")
                # Render the template with the current context and error message
                order_details = order.details.all().order_by('-order_date')  # Use '-id' if no order_date exists
                total_price_before_tax = sum(detail.product.price * detail.quantity for detail in order_details)
                total_price_after_tax = total_price_before_tax * Decimal('1.13')
                return render(request, self.template_name, {
                    'order': order,
                    'form': form,
                    'order_details': order_details,
                    'total_price_before_tax': total_price_before_tax,
                    'total_price_after_tax': total_price_after_tax,
                })

            # Use transaction.atomic to ensure safe updates
            with transaction.atomic():
                order_detail, created = OrderDetail.objects.select_for_update().get_or_create(
                    order=order,
                    product=product,
                    defaults={'quantity': quantity, 'price': product.price}  # Store only the price for one unit
                )
                if not created:
                    # Increment quantity without altering the price
                    order_detail.quantity = F('quantity') + quantity
                    order_detail.save()

                # Update order total price
                order.total_price = F('total_price') + (product.price * quantity)
                order.save()

                # Decrement product stock
                product.quantity_in_stock = F('quantity_in_stock') - quantity
                product.save()

            messages.success(request, f"{quantity} unit(s) of {product.name} added to the order. Price per unit: ${product.price:.2f}")

        # Render the template with updated context instead of redirecting
        order_details = order.details.all().order_by('-order_date')  # Use '-id' if no order_date exists
        total_price_before_tax = sum(detail.product.price * detail.quantity for detail in order_details)
        total_price_after_tax = total_price_before_tax * Decimal('1.13')

        return render(request, self.template_name, {
            'order': order,
            'form': form,
            'order_details': order_details,
            'total_price_before_tax': total_price_before_tax,
            'total_price_after_tax': total_price_after_tax,
        })


class UpdateOrderItemView(LoginRequiredMixin, View):
    def post(self, request, item_id):
        order_detail = get_object_or_404(OrderDetail, od_id=item_id)
        new_quantity = int(request.POST.get('quantity', 1))

        if new_quantity < 1:
            messages.error(request, "Quantity must be at least 1.")
            return HttpResponseRedirect(reverse('create_order'))

        product = order_detail.product
        current_quantity = order_detail.quantity
        quantity_difference = new_quantity - current_quantity

        # Check stock availability if the quantity is being increased
        if quantity_difference > 0 and product.quantity_in_stock < quantity_difference:
            messages.error(request, f"Not enough stock for {product.name}.")
            return HttpResponseRedirect(reverse('create_order'))

        with transaction.atomic():
            # Update product stock
            product.quantity_in_stock -= quantity_difference
            product.save()

            # Update the order detail's quantity
            order_detail.quantity = new_quantity
            order_detail.price = product.price  # Ensure the price remains the unit price
            order_detail.save()

            # Recalculate the total price for the order
            order = order_detail.order
            order.total_price = sum(
                detail.product.price * detail.quantity for detail in order.details.all()
            )
            order.save()

        if quantity_difference > 0:
            messages.success(request, f"Added {quantity_difference} unit(s) of {product.name} to the order.")
        elif quantity_difference < 0:
            messages.success(request, f"Removed {-quantity_difference} unit(s) of {product.name} from the order.")

        return HttpResponseRedirect(reverse('create_order'))


class SubmitOrderView(LoginRequiredMixin, View):
   def post(self, request, *args, **kwargs):
       if 'order_id' in request.session:
           order = get_object_or_404(Order, order_id=request.session['order_id'])


           # Loop through each OrderDetail and update RecentlyPurchasedProduct
           for detail in order.details.all():
               recently_purchased, created = RecentlyPurchasedProduct.objects.get_or_create(
                   product=detail.product
               )
               if not created:
                   recently_purchased.quantity += detail.quantity  # Increment quantity if product already exists
               else:
                   recently_purchased.quantity = detail.quantity  # Set quantity if newly created
               recently_purchased.save()


           # Mark the order as submitted and save
           order.submitted = True
           order.save()
           # Clear the session to start a new order
           del request.session['order_id']


           return redirect('create_order')


@login_required
def delete_order_item(request, item_id):
   # Fetch the order detail object by its id (od_id)
   order_detail = get_object_or_404(OrderDetail, od_id=item_id)
   order = order_detail.order  # Get the associated order
   product = order_detail.product  # Get the associated product


   # Decrease the quantity in the order by 1
   if order_detail.quantity > 1:
       order_detail.quantity -= 1
       order_detail.price -= product.price  # Adjust the price accordingly
       order_detail.save()


       # Increase the product's stock by 1
       product.quantity_in_stock += 1
       product.save()


       # Update the order's total price
       order.total_price -= product.price
       order.save()


       # Optionally, add a message to confirm the update
       messages.success(request, f"1 unit of {product.name} removed from the order.")
   else:
       # If quantity is 1, delete the order detail
       product.quantity_in_stock += order_detail.quantity  # Return all stock
       product.save()
       order.total_price -= order_detail.price  # Adjust the order's total price
       order.save()
       order_detail.delete()


       # Optionally, add a message to confirm deletion
       messages.success(request, f"{product.name} removed from the order.")


   # Redirect back to the CreateOrderView
   return redirect('create_order')

# View for order success page
"""
class OrderSuccessView(View):
   template_name = 'order_success.html'
  
   def get(self, request, *args, **kwargs):
       return render(request, self.template_name)
"""

# DELETES ON ITEM ON CHECKIN BUTTON
def delete_one(request, product_id):
    if request.method == "POST":
        product = get_object_or_404(Product, pk=product_id)
        
        # Check if there is stock to subtract
        if product.quantity_in_stock > 0:
            product.quantity_in_stock -= 1
            product.save()
            messages.success(request, f"Successfully subtracted 1 from {product.name}'s stock.")
        else:
            messages.error(request, f"Cannot subtract. {product.name} is already out of stock.")

    # Redirect back to the check-in page
    return redirect('checkin')  # Replace 'checkin' with the actual name of your check-in view

#checkin views
class CheckinProductView(LoginRequiredMixin, View):
    template_name = 'checkin.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        barcode = request.POST.get('barcode')
        if barcode:
            try:
                # Use a transaction to ensure atomic updates
                with transaction.atomic():
                    product = Product.objects.select_for_update().get(barcode=barcode)
                    product.quantity_in_stock += 1
                    product.save()

                    messages.success(request, f"1 unit of {product.name} added to stock.")
                    # Render template with product details
                    return render(request, self.template_name, {'product': product})

            except Product.DoesNotExist:
                messages.error(request, "Product does not exist. Please add the product first.")
                return redirect('new_product')
        else:
            messages.error(request, "No barcode provided.")

        return render(request, self.template_name)
    
class AddQuantityView(LoginRequiredMixin, View):
    def post(self, request, product_id):
        product = get_object_or_404(Product, product_id=product_id)
        quantity_to_add = int(request.POST.get('quantity_to_add', 1))
        
        if quantity_to_add < 1:
            messages.error(request, "Quantity to add must be at least 1.")
            return redirect('checkin')

        # Update the product stock
        product.quantity_in_stock += quantity_to_add
        product.save()

        messages.success(request, f"{quantity_to_add} unit(s) of {product.name} added to stock.")
        return redirect('checkin')

# Display all orders
class OrderView(AdminRequiredMixin, View):
   template_name = 'order_view.html'


   def get(self, request):
       orders = Order.objects.all()
       return render(request, self.template_name, {'orders': orders})


# Add a new product
class AddProductView(LoginRequiredMixin, View):
    template_name = 'new_product.html'

    def get(self, request):
        # Capture the 'next' parameter from the query string
        next_url = request.GET.get('next', '')
        categories = Category.objects.all()

        # Initialize an empty form or prefill it with query parameters
        initial_data = {
            'name': request.GET.get('name', ''),
            'barcode': request.GET.get('barcode', ''),
            'price': request.GET.get('price', ''),
        }
        form = AddProductForm(initial=initial_data)

        return render(request, self.template_name, {
            'categories': categories,
            'form': form,  # Pass the form to the template
            'next': next_url  # Pass the next URL to the template
        })

    def post(self, request):
        form = AddProductForm(request.POST)
        # Capture the 'next' parameter from the hidden input
        next_url = request.POST.get('next', '')

        if form.is_valid():
            barcode = form.cleaned_data.get('barcode')  # Extract the barcode from the form
            try:
                # Check if a product with the same barcode already exists
                if Product.objects.filter(barcode=barcode).exists():
                    messages.error(request, f"A product with barcode '{barcode}' already exists.")
                    return render(request, self.template_name, {
                        'categories': Category.objects.all(),
                        'form': form,
                        'next': next_url
                    })

                # Save the product if no duplicates found
                form.save()
                messages.success(request, "Product added successfully.")

                # Redirect to the captured 'next' URL or default to 'checkin'
                return redirect(next_url) if next_url else redirect('checkin')
            except IntegrityError:
                messages.error(request, "A product with this barcode or item number already exists.")
            except Exception as e:
                # Handle unexpected errors gracefully
                messages.error(request, f"An unexpected error occurred: {str(e)}")
        else:
            messages.error(request, "Failed to add product. Please check the form fields.")

        # Re-render the form with categories and pass the 'next' URL
        categories = Category.objects.all()
        return render(request, self.template_name, {
            'categories': categories,
            'form': form,
            'next': next_url
        })

# Display inventory
class InventoryView(LoginRequiredMixin, View):
    template_name = 'inventory_display.html'

    def get(self, request):
        # Get filter parameters from the request
        selected_category_id = request.GET.get('category_id', '')
        barcode_query = request.GET.get('barcode_query', '')
        name_query = request.GET.get('name_query', '')

        # Query products based on filters
        products = Product.objects.all().order_by('-name')  # Assuming `id` is the primary key
        if selected_category_id:
            products = products.filter(category_id=selected_category_id)
        if barcode_query:
            products = products.filter(barcode__icontains=barcode_query)
        if name_query:
            products = products.filter(name__icontains=name_query)

        # Paginate the filtered products
        paginator = Paginator(products, 100)  # Show 100 items per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Pass all query parameters and the paginator to the template
        return render(request, self.template_name, {
            'page_obj': page_obj,
            'categories': Category.objects.all(),
            'selected_category_id': selected_category_id,
            'barcode_query': barcode_query,
            'name_query': name_query,
        })


# Edit an existing product
class EditProductView(View):
    template_name = 'edit_product.html'

    def get(self, request, product_id):
        # Get the product to edit
        product = get_object_or_404(Product, product_id=product_id)
        form = EditProductForm(instance=product)

        # Capture the 'next' parameter from the GET request
        next_url = request.GET.get('next', request.META.get('HTTP_REFERER', reverse('inventory_display')))

        return render(request, self.template_name, {
            'form': form,
            'product': product,
            'next': next_url,  # Pass the next URL to the template
        })

    def post(self, request, product_id):
        # Get the product to edit
        product = get_object_or_404(Product, product_id=product_id)
        form = EditProductForm(request.POST, instance=product)

        # Capture the 'next' parameter from the POST data
        next_url = request.POST.get('next', reverse('inventory_display'))

        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")

            # Redirect to the captured 'next' URL if available
            return redirect(next_url)

        # If the form is invalid, re-render the page with the current form and next URL
        return render(request, self.template_name, {
            'form': form,
            'product': product,
            'next': next_url,
        })

      
# View for displaying low-stock items
class LowStockView(AdminRequiredMixin, View):
   template_name = 'low_stock.html'
   threshold = 3


   def get(self, request):
       barcode_query = request.GET.get('barcode_query')
       selected_category_id = request.GET.get('category_id')


       low_stock_products = Product.objects.filter(quantity_in_stock__lt=self.threshold)
       recently_purchased = RecentlyPurchasedProduct.objects.all().order_by('-order_date')
       categories = Category.objects.all()


       if barcode_query:
           low_stock_products = low_stock_products.filter(barcode__icontains=barcode_query)
       if selected_category_id:
           low_stock_products = low_stock_products.filter(category_id=selected_category_id)


       paginator_low_stock = Paginator(low_stock_products, 100)
       page_number_low_stock = request.GET.get('page')
       page_obj_low_stock = paginator_low_stock.get_page(page_number_low_stock)


       paginator_recent = Paginator(recently_purchased, 80)
       page_number_recent = request.GET.get('page_recent')
       page_obj_recent = paginator_recent.get_page(page_number_recent)


       return render(request, self.template_name, {
           'page_obj_low_stock': page_obj_low_stock,
           'page_obj_recent': page_obj_recent,
           'categories': categories,
           'selected_category_id': selected_category_id,
           'barcode_query': barcode_query,
           'threshold': self.threshold,
       })


# Delete a recently purchased product
class DeleteRecentlyPurchasedProductView(LoginRequiredMixin, View):
   def post(self, request, id):  # Use 'id' to match the model's primary key field name
       try:
           recently_purchased = RecentlyPurchasedProduct.objects.get(id=id)
           product_name = recently_purchased.product.name  # Capture the name before deletion
           recently_purchased.delete()
           messages.success(request, f"{product_name} has been deleted from the recently purchased list.")
       except RecentlyPurchasedProduct.DoesNotExist:
           messages.error(request, "The selected product does not exist in the recently purchased list.")
       return redirect('low_stock')


class DeleteAllRecentlyPurchasedView(LoginRequiredMixin, View):
   def post(self, request):
       # Delete all recently purchased products
       RecentlyPurchasedProduct.objects.all().delete()
       messages.success(request, "All recently purchased products have been deleted.")
       return redirect('low_stock')


# Delete an item
@login_required
def delete_item(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    product.delete()
    messages.success(request, f"Product '{product.name}' has been deleted.")

    # Redirect back to inventory page with query parameters
    page = request.POST.get('page', 1)
    category_id = request.POST.get('category_id', '')
    barcode_query = request.POST.get('barcode_query', '')
    name_query = request.POST.get('name_query', '')

    redirect_url = f"{reverse('inventory_display')}?page={page}"
    if category_id:
        redirect_url += f"&category_id={category_id}"
    if barcode_query:
        redirect_url += f"&barcode_query={barcode_query}"
    if name_query:
        redirect_url += f"&name_query={name_query}"

    return redirect(redirect_url)


# Delete all orders
class DeleteAllOrdersView(LoginRequiredMixin, View):
   def post(self, request, *args, **kwargs):
       Order.objects.all().delete()
       request.session['next_order_id'] = 1
       messages.success(request, "All orders have been deleted successfully.")
       return redirect('order_view')


# Item list view
class ItemListView(LoginRequiredMixin,View):
   template_name = 'item_list.html'
   form_class = ItemForm


   def get(self, request):
       form = self.form_class()
       items = Item.objects.all()
       return render(request, self.template_name, {'form': form, 'items': items})


   def post(self, request):
       if 'delete' in request.POST:
           item_id = request.POST.get('item_id')
           item = get_object_or_404(Item, id=item_id)
           item.delete()
           messages.success(request, f"Item '{item.item_name}' has been deleted.")
           return redirect('item_list')
       elif 'update_checked' in request.POST:
           item_id = request.POST.get('item_id')
           is_checked = request.POST.get('is_checked') == 'on'
           item = get_object_or_404(Item, id=item_id)
           item.is_checked = is_checked
           item.save()
           return redirect('item_list')
       else:
           form = self.form_class(request.POST)
           if form.is_valid():
               form.save()
               return redirect('item_list')


       items = Item.objects.all()
       return render(request, self.template_name, {'form': form, 'items': items})





