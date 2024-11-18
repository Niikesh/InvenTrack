from email import message
from unicodedata import category
from django.shortcuts import get_object_or_404, render,redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from ims_django.settings import MEDIA_ROOT, MEDIA_URL
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpResponse
from imsApp.forms import SaveStock, UserRegistration, UpdateProfile, UpdatePasswords, SaveCategory, SaveProduct, SaveInvoice, SaveInvoiceItem
from imsApp.models import Category, Product, Stock, Invoice, Invoice_Item
from cryptography.fernet import Fernet
from django.conf import settings
from .inventory_algo import forecast_demand, calculate_replenishment
from django.db.models import Sum
import json
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import io
import base64
import pandas as pd
from django.utils import timezone
import csv
import os
from django.template.loader import render_to_string
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas

context = {
    'page_title' : 'File Management System',
}
#login
def login_user(request):
    logout(request)
    resp = {"status":'failed','msg':''}
    username = ''
    password = ''
    if request.POST:
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                resp['status']='success'
            else:
                resp['msg'] = "Incorrect username or password"
        else:
            resp['msg'] = "Incorrect username or password"
    return HttpResponse(json.dumps(resp),content_type='application/json')

#Logout
def logoutuser(request):
    logout(request)
    return redirect('/')

@login_required
def home(request):
    context['page_title'] = 'Home'
    context['categories'] = Category.objects.count()
    context['products'] = Product.objects.count()
    context['sales'] = Invoice.objects.count()
    return render(request, 'home.html',context)

def registerUser(request):
    user = request.user
    if user.is_authenticated:
        return redirect('home-page')
    context['page_title'] = "Register User"
    if request.method == 'POST':
        data = request.POST
        form = UserRegistration(data)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            pwd = form.cleaned_data.get('password1')
            loginUser = authenticate(username= username, password = pwd)
            login(request, loginUser)
            return redirect('home-page')
        else:
            context['reg_form'] = form

    return render(request,'register.html',context)

@login_required
def update_profile(request):
    context['page_title'] = 'Update Profile'
    user = User.objects.get(id = request.user.id)
    if not request.method == 'POST':
        form = UpdateProfile(instance=user)
        context['form'] = form
        print(form)
    else:
        form = UpdateProfile(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile has been updated")
            return redirect("profile")
        else:
            context['form'] = form
            
    return render(request, 'manage_profile.html',context)


@login_required
def update_password(request):
    context['page_title'] = "Update Password"
    if request.method == 'POST':
        form = UpdatePasswords(user = request.user, data= request.POST)
        if form.is_valid():
            form.save()
            messages.success(request,"Your Account Password has been updated successfully")
            update_session_auth_hash(request, form.user)
            return redirect("profile")
        else:
            context['form'] = form
    else:
        form = UpdatePasswords(request.POST)
        context['form'] = form
    return render(request,'update_password.html',context)


@login_required
def profile(request):
    context['page_title'] = 'Profile'
    return render(request, 'profile.html',context)


# Category
@login_required
def category_mgt(request):
    context['page_title'] = "Product Categories"
    categories = Category.objects.all()
    context['categories'] = categories

    return render(request, 'category_mgt.html', context)

@login_required
def save_category(request):
    resp = {'status':'failed','msg':''}
    if request.method == 'POST':
        if (request.POST['id']).isnumeric():
            category = Category.objects.get(pk=request.POST['id'])
        else:
            category = None
        if category is None:
            form = SaveCategory(request.POST)
        else:
            form = SaveCategory(request.POST, instance= category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category has been saved successfully.')
            resp['status'] = 'success'
        else:
            for fields in form:
                for error in fields.errors:
                    resp['msg'] += str(error + "<br>")
    else:
        resp['msg'] = 'No data has been sent.'
    return HttpResponse(json.dumps(resp), content_type = 'application/json')

@login_required
def manage_category(request, pk=None):
    context['page_title'] = "Manage Category"
    if not pk is None:
        category = Category.objects.get(id = pk)
        context['category'] = category
    else:
        context['category'] = {}

    return render(request, 'manage_category.html', context)

@login_required
def delete_category(request):
    resp = {'status':'failed', 'msg':''}

    if request.method == 'POST':
        try:
            category = Category.objects.get(id = request.POST['id'])
            category.delete()
            messages.success(request, 'Category has been deleted successfully')
            resp['status'] = 'success'
        except Exception as err:
            resp['msg'] = 'Category has failed to delete'
            print(err)

    else:
        resp['msg'] = 'Category has failed to delete'
    
    return HttpResponse(json.dumps(resp), content_type="application/json")
        
# product
@login_required
def product_mgt(request):
    context['page_title'] = "Product List"
    products = Product.objects.all()
    context['products'] = products

    return render(request, 'product_mgt.html', context)

@login_required
def save_product(request):
    resp = {'status':'failed','msg':''}
    if request.method == 'POST':
        if (request.POST['id']).isnumeric():
            product = Product.objects.get(pk=request.POST['id'])
        else:
            product = None
        if product is None:
            form = SaveProduct(request.POST)
        else:
            form = SaveProduct(request.POST, instance= product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product has been saved successfully.')
            resp['status'] = 'success'
        else:
            for fields in form:
                for error in fields.errors:
                    resp['msg'] += str(error + "<br>")
    else:
        resp['msg'] = 'No data has been sent.'
    return HttpResponse(json.dumps(resp), content_type = 'application/json')

@login_required
def manage_product(request, pk=None):
    context['page_title'] = "Manage Product"
    if not pk is None:
        product = Product.objects.get(id = pk)
        context['product'] = product
    else:
        context['product'] = {}

    return render(request, 'manage_product.html', context)

@login_required
def delete_product(request):
    resp = {'status':'failed', 'msg':''}

    if request.method == 'POST':
        try:
            product = Product.objects.get(id = request.POST['id'])
            product.delete()
            messages.success(request, 'Product has been deleted successfully')
            resp['status'] = 'success'
        except Exception as err:
            resp['msg'] = 'Product has failed to delete'
            print(err)

    else:
        resp['msg'] = 'Product has failed to delete'
    
    return HttpResponse(json.dumps(resp), content_type="application/json")

#Inventory
@login_required
def inventory(request):
    context['page_title'] = 'Inventory'

    products = Product.objects.all()

    for product in products:
        if product.count_inventory() <= 0:  # If stock is less than or equal to 0
            messages.warning(request, f'Product {product.name} is out of stock!')
            
    context['products'] = products

    return render(request, 'inventory.html', context)

#Inventory History
@login_required
def inv_history(request, pk=None):
    context = {}
    context['page_title'] = 'Inventory History'
    
    if pk is None:
        messages.error(request, "Product ID is not recognized")
        return redirect('inventory-page')
    
    product = get_object_or_404(Product, id=pk)
    stocks = Stock.objects.filter(product=product)
    
    # Get date range from GET parameters or set defaults
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date:
        start_date = (timezone.now() - timezone.timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = timezone.now().strftime('%Y-%m-%d')
    
    # Fetch individual sales data within the date range
    sales_historic_data = (
        Invoice_Item.objects.filter(product=product, invoice__date_created__date__range=[start_date, end_date])
        .values('invoice__date_created__date', 'quantity')  # Individual quantities
        .order_by('invoice__date_created__date')
    )
    
    # Prepare data for the chart
    sales_chart_data = {
        "dates": [item['invoice__date_created__date'].strftime("%Y-%m-%d") for item in sales_historic_data],
        "quantities": [item['quantity'] for item in sales_historic_data],
    }
    
    # Save data to CSV
    save_sales_data_to_csv(sales_chart_data)
    
    # Load data back from CSV for graph generation
    sales_chart_data = load_sales_data_from_csv()
    
    # Generate graph
    if sales_chart_data['dates'] and sales_chart_data['quantities']:
        plt.figure(figsize=(12, 6))
        plt.plot(
            sales_chart_data['dates'], 
            sales_chart_data['quantities'], 
            marker='o', linestyle='-', color='blue'
        )
        plt.title(f'Day-to-Day Sales for {product.name}', fontsize=16)
        plt.xlabel('Date', fontsize=14)
        plt.ylabel('Quantity Sold', fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()

        # Save plot to a bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        image_png = buf.getvalue()
        buf.close()

        # Encode the image to base64
        plot_base64 = base64.b64encode(image_png).decode('utf-8')
        plot_url = f"data:image/png;base64,{plot_base64}"

        # print(plot_url)
    else:
        plot_url = None
        messages.info(request, "No sales data available to display the chart.")

    # Add data to context
    context['product'] = product
    context['stocks'] = stocks
    context['plot_url'] = plot_url
    context['start_date'] = start_date
    context['end_date'] = end_date
    
    return render(request, 'inventory-history.html', context)


    
#Stock Form
@login_required
def manage_stock(request,pid = None ,pk = None):
    if pid is None:
        messages.error(request, "Product ID is not recognized")
        return redirect('inventory-page')
    context['pid'] = pid
    if pk is None:
        context['page_title'] = "Add New Stock"
        context['stock'] = {}
    else:
        context['page_title'] = "Manage New Stock"
        stock = Stock.objects.get(id = pk)
        context['stock'] = stock
    
    return render(request, 'manage_stock.html', context )

@login_required
def save_stock(request):
    resp = {'status':'failed','msg':''}
    if request.method == 'POST':
        if (request.POST['id']).isnumeric():
            stock = Stock.objects.get(pk=request.POST['id'])
        else:
            stock = None
        if stock is None:
            form = SaveStock(request.POST)
        else:
            form = SaveStock(request.POST, instance= stock)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stock has been saved successfully.')
            resp['status'] = 'success'
        else:
            for fields in form:
                for error in fields.errors:
                    resp['msg'] += str(error + "<br>")
    else:
        resp['msg'] = 'No data has been sent.'
    return HttpResponse(json.dumps(resp), content_type = 'application/json')

@login_required
def delete_stock(request):
    resp = {'status':'failed', 'msg':''}

    if request.method == 'POST':
        try:
            stock = Stock.objects.get(id = request.POST['id'])
            stock.delete()
            messages.success(request, 'Stock has been deleted successfully')
            resp['status'] = 'success'
        except Exception as err:
            resp['msg'] = 'Stock has failed to delete'
            print(err)

    else:
        resp['msg'] = 'Stock has failed to delete'
    
    return HttpResponse(json.dumps(resp), content_type="application/json")


@login_required
def sales_mgt(request):
    context['page_title'] = 'Sales'
    products = Product.objects.filter(status = 1).all()
    context['products'] = products
    return render(request,'sales.html', context)


def get_product(request,pk = None):
    resp = {'status':'failed','data':{},'msg':''}
    if pk is None:
        resp['msg'] = 'Product ID is not recognized'
    else:
        product = Product.objects.get(id = pk)
        resp['data']['product'] = str(product.code + " - " + product.name)
        resp['data']['id'] = product.id
        resp['data']['price'] = product.price
        resp['status'] = 'success'
    
    return HttpResponse(json.dumps(resp),content_type="application/json")


def save_sales(request):
    resp = {'status':'failed', 'msg' : ''}
    id = 2
    if request.method == 'POST':
        pids = request.POST.getlist('pid[]')
        invoice_form = SaveInvoice(request.POST)
        if invoice_form.is_valid():
            invoice_form.save()
            invoice = Invoice.objects.last()
            for pid in pids:
                data = {
                    'invoice':invoice.id,
                    'product':pid,
                    'quantity':request.POST['quantity['+str(pid)+']'],
                    'price':request.POST['price['+str(pid)+']'],
                }
                print(data)
                ii_form = SaveInvoiceItem(data=data)
                # print(ii_form.data)
                if ii_form.is_valid():
                    ii_form.save()
                else:
                    for fields in ii_form:
                        for error in fields.errors:
                            resp['msg'] += str(error + "<br>")
                    break
            messages.success(request, "Sale Transaction has been saved.")
            resp['status'] = 'success'
            # invoice.delete()
        else:
            for fields in invoice_form:
                for error in fields.errors:
                    resp['msg'] += str(error + "<br>")

    return HttpResponse(json.dumps(resp),content_type="application/json")

#download invoice
def download_invoice_pdf(request, invoice_id):
    try:
        # Fetch the invoice and related invoice items
        invoice = Invoice.objects.get(id=invoice_id)
        invoice_items = Invoice_Item.objects.filter(invoice=invoice)

        # Create a response object with PDF content-type
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.id}.pdf"'

        # Create a canvas object for the PDF
        c = canvas.Canvas(response, pagesize=letter)

        # Set up the title and other basic elements
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, f"Invoice #{invoice.id}")
        c.setFont("Helvetica", 12)
        c.drawString(100, 730, f"Date: {invoice.date_created.strftime('%Y-%m-%d')}")
        c.drawString(100, 710, f"Customer: {invoice.customer}")

        # Table headers
        c.setFont("Helvetica-Bold", 10)
        c.drawString(100, 680, "Product")
        c.drawString(300, 680, "Quantity")
        c.drawString(400, 680, "Price")
        c.drawString(500, 680, "Total")

        # Table data (Invoice Items)
        y_position = 660
        c.setFont("Helvetica", 10)
        for item in invoice_items:
            c.drawString(100, y_position, item.product.name)  # Assuming the product has a `name` field
            c.drawString(300, y_position, str(item.quantity))
            c.drawString(400, y_position, f"${item.price:.2f}")
            c.drawString(500, y_position, f"${item.quantity * item.price:.2f}")
            y_position -= 20  # Move to the next row

        # Total amount
        total_amount = sum(item.quantity * item.price for item in invoice_items)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y_position - 20, f"Total Amount: ${total_amount:.2f}")

        # Close the PDF document
        c.showPage()
        c.save()

        return response

    except Invoice.DoesNotExist:
        return HttpResponse("Invoice not found.", status=404)
    
    
#invoices
@login_required
def invoices(request):
    invoice =  Invoice.objects.all()
    context['page_title'] = 'Invoices'
    context['invoices'] = invoice

    return render(request, 'invoices.html', context)

@login_required
def delete_invoice(request):
    resp = {'status':'failed', 'msg':''}

    if request.method == 'POST':
        try:
            invoice = Invoice.objects.get(id = request.POST['id'])
            invoice.delete()
            messages.success(request, 'Invoice has been deleted successfully')
            resp['status'] = 'success'
        except Exception as err:
            resp['msg'] = 'Invoice has failed to delete'
            print(err)

    else:
        resp['msg'] = 'Invoice has failed to delete'
    
    return HttpResponse(json.dumps(resp), content_type="application/json")

def invoice_detail(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    items = invoice.invoice_item_set.all()  # All items related to the invoice
    total = invoice.total
    item_count = invoice.item_count()  # Using the method to get the total item count
    
    return render(request, 'invoice-bill.html', {
        'invoice': invoice,
        'items': items,
        'total': total,
        'item_count': item_count
    })


@login_required
def inventory_predict(request, product_id):
    # Get the specific product
    product = get_object_or_404(Product, id=product_id)

    # Forecast demand for the next 30 days
    forecasted_demand = forecast_demand(product)

    # Calculate required replenishment based on forecast
    replenishment_needed = calculate_replenishment(product)

    # Pass results to the template
    context = {
        'product': product,
        'forecasted_demand': forecasted_demand,
        'replenishment_needed': replenishment_needed,
    }
    return render(request, 'inventory_predict.html', context)


# Function to save sales data from a CSV file
def save_sales_data_to_csv(data, filename='sales_data.csv'):
    file_path = os.path.join('C:\\Users\\Dell\\Downloads\\ims_django_0 (2)\\ims_django\\imsApp\\data', 'csv', filename)
  # Replace 'path_to_save_csv' with your desired location
    os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Create directories if they don't exist
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Date', 'Quantity'])  # CSV Header
        for date, quantity in zip(data['dates'], data['quantities']):
            writer.writerow([date, quantity])
    return file_path

# Function to load sales data from a CSV file
def load_sales_data_from_csv(filename='sales_data.csv'):
    file_path = os.path.join('C:\\Users\\Dell\\Downloads\\ims_django_0 (2)\\ims_django\\imsApp\\data', 'csv', filename)
 # Adjust this path as needed
    sales_data = {'dates': [], 'quantities': []}
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                sales_data['dates'].append(row['Date'])
                sales_data['quantities'].append(int(float(row['Quantity'])))  # Convert quantity to integer
    except FileNotFoundError:
        sales_data = {'dates': [], 'quantities': []}
    return sales_data



def render_chart(request):
    # Load CSV data into a pandas DataFrame
    data = pd.read_csv('C:\\Users\\Dell\\Downloads\\ims_django_0 (2)\\ims_django\\imsApp\\data\\csv\\sales_data.csv')  # Adjust the file path as needed

    # Create the plot
    fig, ax = plt.subplots()
    ax.plot(data['Date'], data['Quantity'])

    # Set labels and title for the chart
    ax.set(xlabel='Date', ylabel='Quantity', title='Simple Line Chart')

    # Save the plot to a BytesIO object (in-memory file)
    img_buf = io.BytesIO()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(img_buf, format='png')  # Save the figure as a PNG image in memory
    img_buf.seek(0)

    # Serve the image as a response
    response = HttpResponse(img_buf, content_type='image/png')
    response['Content-Disposition'] = 'inline; filename="chart.png"'
    return response