from django_plotly_dash import DjangoDash
import dash
from dash import dcc, html
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Create a simple Traffic Dashboard app
traffic_app = DjangoDash('TrafficDashboard')

traffic_app.layout = html.Div([
    html.H1('Traffic Dashboard'),
    html.P('This is a test dashboard to verify Django Plotly Dash integration.'),
    dcc.Graph(
        id='example-graph',
        figure={
            'data': [
                {'x': [1, 2, 3], 'y': [4, 1, 2], 'type': 'bar', 'name': 'SF'},
                {'x': [1, 2, 3], 'y': [2, 4, 5], 'type': 'bar', 'name': 'NYC'},
            ],
            'layout': {
                'title': 'Sample Data'
            }
        }
    )
])

# Create a simple Geographic Dashboard app
geo_app = DjangoDash('GeoDashboard')

# Generate sample data for the map
countries = ['United States', 'United Kingdom', 'Canada', 'Australia', 
            'Germany', 'France', 'India', 'Japan', 'Brazil', 'China']
visits = np.random.randint(500, 5000, size=len(countries))
df_geo = pd.DataFrame({'country': countries, 'visits': visits})

geo_app.layout = html.Div([
    html.H1('Geographic Dashboard'),
    html.P('Worldwide distribution of website visitors'),
    dcc.Graph(
        id='world-map',
        figure=px.choropleth(
            df_geo, 
            locations='country',
            locationmode='country names',
            color='visits',
            hover_name='country',
            color_continuous_scale=px.colors.sequential.Blues,
            title='Visitor Distribution by Country'
        )
    )
])

# Create a simple Conversion Dashboard app
conversion_app = DjangoDash('ConversionDashboard')

# Generate sample date range
dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
conversion_rates = np.random.uniform(1, 8, size=len(dates))
df_conv = pd.DataFrame({'date': dates, 'conversion_rate': conversion_rates})

conversion_app.layout = html.Div([
    html.H1('Conversion Dashboard'),
    html.P('Conversion metrics and trends'),
    dcc.Graph(
        id='conversion-trend',
        figure=px.line(
            df_conv, 
            x='date', 
            y='conversion_rate',
            title='Conversion Rate Over Time',
            labels={'conversion_rate': 'Conversion Rate (%)', 'date': 'Date'}
        )
    ),
    html.Div([
        html.H3('Conversion by Type'),
        dcc.Graph(
            id='conversion-by-type',
            figure=px.pie(
                names=['Demo Requests', 'Virtual Assistant', 'Event Registrations'],
                values=[350, 280, 170],
                title='Conversion Distribution by Type',
                hole=0.4
            )
        )
    ])
])