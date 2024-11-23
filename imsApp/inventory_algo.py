
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import timedelta
from .models import Invoice_Item

#demand forecasting algo
def forecast_demand(product, days=30):
    """
    Forecasts demand for a product using a moving average or linear regression.
    - `product`: the Product object
    - `days`: number of days to forecast
    """
    # Fetch historical sales data from Invoice_Item
    invoice_items = Invoice_Item.objects.filter(product=product).order_by('invoice__date_created')
    
    # Extract sales data (quantity) and dates
    sales_data = []
    dates = []
    for item in invoice_items:
        sales_data.append(item.quantity)
        dates.append(item.invoice.date_created)

    # If there's not enough data for forecasting, use a simple moving average
    if len(sales_data) < 10:
        avg_sales = np.mean(sales_data)
        return avg_sales * days  # Simple forecast by multiplying the average sales by the forecast period

    # Use linear regression for forecasting
    regressor = LinearRegression()

    # Convert dates to a numeric format (days since the first sale)
    days_since_start = [(date - dates[0]).days for date in dates]

    # Reshape for regression
    X = np.array(days_since_start).reshape(-1, 1)
    y = np.array(sales_data)

    # Fit the model
    regressor.fit(X, y)

    # Predict future demand
    future_dates = np.array([len(sales_data) + i for i in range(1, days+1)]).reshape(-1, 1)
    predicted_demand = regressor.predict(future_dates)
    
    # Sum the predicted demand for the given forecast period
    return max(0,sum(predicted_demand))


#inventory repleshment algo
def calculate_replenishment(product):
    """
    Calculates the required inventory replenishment based on forecasted demand and current stock.
    - `product`: the Product object
    """
    # Calculate forecasted demand for the next 30 days
    forecasted_demand = forecast_demand(product, days=30)
    
    # Get the current inventory level
    current_inventory = product.count_inventory()
    
    # Define the safety stock (the buffer stock to avoid stockouts)
    safety_stock = 50  # This is an arbitrary number. It should be based on your business needs.
    
    # Define the reorder point (the inventory level at which we reorder)
    reorder_point = forecasted_demand * 0.5  # For example, reorder when 50% of the forecasted demand is left
    
    # Calculate how much stock needs to be replenished
    if current_inventory < reorder_point:
        replenishment_needed = forecasted_demand + safety_stock - current_inventory
        return replenishment_needed
    else:
        return 0  # No replenishment needed

