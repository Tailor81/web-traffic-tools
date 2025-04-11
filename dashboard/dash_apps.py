# dashboard/dash_apps.py
from django_plotly_dash import DjangoDash
from dash import dcc, html, Input, Output, callback_context, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from plotly.subplots import make_subplots
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OneHotEncoder
import statsmodels.api as sm
from statsmodels.tsa.arima.model import ARIMA


# Import models from log_analyzer app
from log_analyzer.models import LogFile, LogEntry

# Function to fetch log data from database
def get_log_data(days=30, log_file_id=None):
    """
    Fetch log data from database
    
    Args:
        days: Number of days of data to fetch
        log_file_id: Optional specific log file ID to filter by
    
    Returns:
        Pandas DataFrame with log data
    """
    from django.utils import timezone
    from django.db.models import Count
    
    # Calculate date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Base queryset
    query = LogEntry.objects.filter(timestamp__gte=start_date)
    
    # Filter by log file if specified
    if log_file_id:
        query = query.filter(log_file_id=log_file_id)
    
    # Convert query to list of dictionaries
    data = list(query.values(
        'timestamp', 'ip_address', 'http_method', 
        'resource', 'status_code', 'country', 'page_category'
    ))
    
    # If no data, return empty DataFrame with expected columns
    if not data:
        return pd.DataFrame(columns=[
            'timestamp', 'ip_address', 'http_method', 
            'resource', 'status_code', 'country', 'page_category'
        ])
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    return df

# Create a Traffic Dashboard
traffic_app = DjangoDash('TrafficDashboard')

traffic_app.layout = html.Div([
    html.H1("Traffic Analysis Dashboard", className="text-center mb-4"),
    html.Div([
        html.Label("Select Date Range:"),
        dcc.Dropdown(
            id='date-range',
            options=[
                {'label': 'Last 7 Days', 'value': 7},
                {'label': 'Last 14 Days', 'value': 14},
                {'label': 'Last 30 Days', 'value': 30},
                {'label': 'Last 90 Days', 'value': 90},
                {'label': 'All Time', 'value': 3650},
            ],
            value=30,
            clearable=False,
            className="mb-4",
            style={'width': '300px'}
        ),
        html.Label("Select Log File (Optional):"),
        dcc.Dropdown(
            id='log-file-selector',
            options=[
                {'label': 'All Log Files', 'value': 'all'}
            ],
            value='all',
            clearable=False,
            className="mb-4",
            style={'width': '300px'}
        ),
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Total Traffic"),
                html.Div(id="total-visits-value", className="display-5")
            ], className="card-body text-center")
        ], className="card shadow-sm mb-4", style={'width': '23%', 'display': 'inline-block', 'margin': '0 1%'}),
        
        html.Div([
            html.Div([
                html.H5("Unique Visitors"),
                html.Div(id="unique-visitors-value", className="display-5")
            ], className="card-body text-center")
        ], className="card shadow-sm mb-4", style={'width': '23%', 'display': 'inline-block', 'margin': '0 1%'}),
        
        html.Div([
            html.Div([
                html.H5("Success Rate"),
                html.Div(id="success-rate-value", className="display-5")
            ], className="card-body text-center")
        ], className="card shadow-sm mb-4", style={'width': '23%', 'display': 'inline-block', 'margin': '0 1%'}),
        
        html.Div([
            html.Div([
                html.H5("Error Rate"),
                html.Div(id="error-rate-value", className="display-5")
            ], className="card-body text-center")
        ], className="card shadow-sm mb-4", style={'width': '23%', 'display': 'inline-block', 'margin': '0 1%'}),
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Traffic Over Time"),
                dcc.Graph(id="traffic-time-graph")
            ], className="card-body")
        ], className="card shadow-sm mb-4 px-0")
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Page Categories"),
                dcc.Graph(id="category-pie-chart")
            ], className="card-body")
        ], className="card shadow-sm mb-4", style={'width': '48%', 'display': 'inline-block', 'margin': '0 1%'}),
        
        html.Div([
            html.Div([
                html.H5("HTTP Status Codes"),
                dcc.Graph(id="status-bar-chart")
            ], className="card-body")
        ], className="card shadow-sm mb-4", style={'width': '48%', 'display': 'inline-block', 'margin': '0 1%'}),
    ], className="mb-4 px-4")
], style={'width': '100%', 'max-width': '100%', 'padding': '0', 'margin': '0'})

@traffic_app.callback(
    [Output('log-file-selector', 'options'),
     Output('total-visits-value', 'children'),
     Output('unique-visitors-value', 'children'),
     Output('success-rate-value', 'children'),
     Output('error-rate-value', 'children'),
     Output('traffic-time-graph', 'figure'),
     Output('category-pie-chart', 'figure'),
     Output('status-bar-chart', 'figure')],
    [Input('date-range', 'value'),
     Input('log-file-selector', 'value')]
)
def update_traffic_dashboard(days, log_file_id):
    # Get available log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    log_file_options = [{'label': 'All Log Files', 'value': 'all'}]
    log_file_options.extend([{'label': log['name'], 'value': log['id']} for log in log_files])
    
    # Get log data
    log_file_id_filter = None if log_file_id == 'all' else int(log_file_id)
    df = get_log_data(days=days, log_file_id=log_file_id_filter)
    
    # Handle empty data case
    if len(df) == 0:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            annotations=[{
                'text': 'No data available for the selected period',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }]
        )
        
        return (
            log_file_options,
            "0",
            "0",
            "0%",
            "0%",
            empty_fig,
            empty_fig,
            empty_fig
        )
    
    # Calculate metrics
    total_visits = len(df)
    unique_visitors = df['ip_address'].nunique()
    success_requests = len(df[df['status_code'] < 400])
    error_requests = len(df[df['status_code'] >= 400])
    success_rate = (success_requests / total_visits) * 100 if total_visits > 0 else 0
    error_rate = (error_requests / total_visits) * 100 if total_visits > 0 else 0
    
    # Traffic over time graph
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily_traffic = df.groupby('date').size().reset_index(name='count')
    time_fig = px.line(
        daily_traffic, 
        x='date', 
        y='count',
        title='Daily Traffic',
        labels={'count': 'Visits', 'date': 'Date'},
        height=400  # Set a fixed height
    )
    time_fig.update_layout(
        hovermode='x',
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    # Page categories pie chart
    category_counts = df['page_category'].value_counts().reset_index()
    category_counts.columns = ['category', 'count']
    category_fig = px.pie(
        category_counts,
        values='count',
        names='category',
        title='Traffic by Page Category',
        height=400  # Set a fixed height
    )
    category_fig.update_traces(textposition='inside', textinfo='percent+label')
    category_fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white'
    )
    
    # Status codes bar chart
    status_counts = df['status_code'].value_counts().reset_index()
    status_counts.columns = ['status', 'count']
    
    # Color mapping for status codes
    status_colors = {
        200: '#28a745',  # Success (green)
        301: '#ffc107',  # Redirect (yellow)
        302: '#ffc107',  # Redirect (yellow)
        304: '#17a2b8',  # Not Modified (info)
        400: '#fd7e14',  # Bad Request (orange)
        404: '#dc3545',  # Not Found (red)
        500: '#dc3545',  # Server Error (red)
    }
    
    # Default color for other status codes
    default_color = '#6c757d'  # Gray
    
    # Create color list for each status code
    colors = [status_colors.get(status, default_color) for status in status_counts['status']]
    
    status_fig = px.bar(
        status_counts,
        x='status',
        y='count',
        title='HTTP Status Codes',
        labels={'count': 'Count', 'status': 'Status Code'},
        color='status',
        color_discrete_map={str(code): color for code, color in status_colors.items()},
        height=400  # Set a fixed height
    )
    status_fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    return (
        log_file_options,
        f"{total_visits:,}",
        f"{unique_visitors:,}",
        f"{success_rate:.1f}%",
        f"{error_rate:.1f}%",
        time_fig,
        category_fig,
        status_fig
    )

# Create a Geographic Dashboard
geo_app = DjangoDash('GeoDashboard')

geo_app.layout = html.Div([
    html.H1("Geographic Distribution Dashboard", className="text-center mb-4"),
    html.Div([
        html.Label("Select Date Range:"),
        dcc.Dropdown(
            id='geo-date-range',
            options=[
                {'label': 'Last 7 Days', 'value': 7},
                {'label': 'Last 14 Days', 'value': 14},
                {'label': 'Last 30 Days', 'value': 30},
                {'label': 'Last 90 Days', 'value': 90},
                {'label': 'All Time', 'value': 3650},
            ],
            value=30,
            clearable=False,
            className="mb-4",
            style={'width': '300px'}
        ),
        html.Label("Select Log File (Optional):"),
        dcc.Dropdown(
            id='geo-log-file-selector',
            options=[
                {'label': 'All Log Files', 'value': 'all'}
            ],
            value='all',
            clearable=False,
            className="mb-4",
            style={'width': '300px'}
        ),
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Countries"),
                dcc.Graph(id="country-bar-chart")
            ], className="card-body")
        ], className="card shadow-sm mb-4 px-0")
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Traffic by Country - Map View"),
                dcc.Graph(id="country-map")
            ], className="card-body")
        ], className="card shadow-sm mb-4 px-0")
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Top Countries by Page Category"),
                dcc.Graph(id="country-category-heatmap")
            ], className="card-body")
        ], className="card shadow-sm mb-4 px-0")
    ], className="mb-4 px-4")
], style={'width': '100%', 'max-width': '100%', 'padding': '0', 'margin': '0'})

@geo_app.callback(
    [Output('geo-log-file-selector', 'options'),
     Output('country-bar-chart', 'figure'),
     Output('country-map', 'figure'),
     Output('country-category-heatmap', 'figure')],
    [Input('geo-date-range', 'value'),
     Input('geo-log-file-selector', 'value')]
)
def update_geo_dashboard(days, log_file_id):
    # Get available log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    log_file_options = [{'label': 'All Log Files', 'value': 'all'}]
    log_file_options.extend([{'label': log['name'], 'value': log['id']} for log in log_files])
    
    # Get log data
    log_file_id_filter = None if log_file_id == 'all' else int(log_file_id)
    df = get_log_data(days=days, log_file_id=log_file_id_filter)
    
    # Handle empty data case
    if len(df) == 0:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            annotations=[{
                'text': 'No data available for the selected period',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }]
        )
        
        return (
            log_file_options,
            empty_fig,
            empty_fig,
            empty_fig
        )
    
    # Country bar chart
    country_counts = df['country'].value_counts().reset_index()
    country_counts.columns = ['country', 'count']
    country_counts = country_counts.sort_values('count', ascending=False).head(10)
    
    country_bar_fig = px.bar(
        country_counts,
        y='country',
        x='count',
        title='Top 10 Countries by Traffic',
        labels={'count': 'Visits', 'country': 'Country'},
        orientation='h',
        color='count',
        color_continuous_scale='Blues',
        height=500
    )
    country_bar_fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    # Country map
    map_data = df['country'].value_counts().reset_index()
    map_data.columns = ['country', 'count']
    
    country_map_fig = px.choropleth(
        map_data,
        locations='country',
        locationmode='country names',
        color='count',
        hover_name='country',
        color_continuous_scale='Blues',
        title='Visitor Distribution by Country',
        height=600
    )
    
    country_map_fig.update_layout(
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type='natural earth'
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor='white'
    )
    
    # Country-category heatmap
    if 'page_category' in df.columns and len(df) > 0:
        # Get top 10 countries and all categories
        top_countries = country_counts['country'].tolist()
        all_categories = df['page_category'].unique()
        
        # Create cross-tabulation for heatmap
        heatmap_data = pd.crosstab(
            df['country'], 
            df['page_category']
        ).reset_index()
        
        # Filter for top countries
        heatmap_data = heatmap_data[heatmap_data['country'].isin(top_countries)]
        
        # Melt for heatmap format
        heatmap_data = pd.melt(
            heatmap_data, 
            id_vars=['country'], 
            value_vars=all_categories,
            var_name='category', 
            value_name='count'
        )
        
        heatmap_fig = px.density_heatmap(
            heatmap_data,
            x='category',
            y='country',
            z='count',
            title='Page Categories by Country',
            labels={'category': 'Page Category', 'country': 'Country', 'count': 'Visits'},
            color_continuous_scale='Blues',
            height=500
        )
        heatmap_fig.update_layout(
            margin=dict(l=20, r=20, t=40, b=20),
            paper_bgcolor='white'
        )
    else:
        # Fallback empty heatmap
        heatmap_fig = go.Figure()
        heatmap_fig.update_layout(
            title='Page Categories by Country',
            annotations=[{
                'text': 'No category data available',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }],
            height=500,
            margin=dict(l=20, r=20, t=40, b=20),
            paper_bgcolor='white'
        )
    
    return (
        log_file_options,
        country_bar_fig,
        country_map_fig,
        heatmap_fig
    )

# Create a Conversion Dashboard
conversion_app = DjangoDash('ConversionDashboard')

conversion_app.layout = html.Div([
    html.H1("Conversion Metrics Dashboard", className="text-center mb-4"),
    html.Div([
        html.Label("Select Date Range:"),
        dcc.Dropdown(
            id='conv-date-range',
            options=[
                {'label': 'Last 7 Days', 'value': 7},
                {'label': 'Last 14 Days', 'value': 14},
                {'label': 'Last 30 Days', 'value': 30},
                {'label': 'Last 90 Days', 'value': 90},
                {'label': 'All Time', 'value': 3650},
            ],
            value=30,
            clearable=False,
            className="mb-4",
            style={'width': '300px'}
        ),
        html.Label("Select Log File (Optional):"),
        dcc.Dropdown(
            id='conv-log-file-selector',
            options=[
                {'label': 'All Log Files', 'value': 'all'}
            ],
            value='all',
            clearable=False,
            className="mb-4",
            style={'width': '300px'}
        ),
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Conversion Statistics"),
                html.Div(id="conversion-stats")
            ], className="card-body")
        ], className="card shadow-sm mb-4 px-0")
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Conversion Funnel"),
                dcc.Graph(id="conversion-funnel")
            ], className="card-body")
        ], className="card shadow-sm mb-4", style={'width': '48%', 'display': 'inline-block', 'margin': '0 1%'}),
        
        html.Div([
            html.Div([
                html.H5("Conversion by Country"),
                dcc.Graph(id="conversion-by-country")
            ], className="card-body")
        ], className="card shadow-sm mb-4", style={'width': '48%', 'display': 'inline-block', 'margin': '0 1%'}),
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Conversion Rate Over Time"),
                dcc.Graph(id="conversion-time-series")
            ], className="card-body")
        ], className="card shadow-sm mb-4 px-0")
    ], className="mb-4 px-4")
], style={'width': '100%', 'max-width': '100%', 'padding': '0', 'margin': '0'})

@conversion_app.callback(
    [Output('conv-log-file-selector', 'options'),
     Output('conversion-stats', 'children'),
     Output('conversion-funnel', 'figure'),
     Output('conversion-by-country', 'figure'),
     Output('conversion-time-series', 'figure')],
    [Input('conv-date-range', 'value'),
     Input('conv-log-file-selector', 'value')]
)
def update_conversion_dashboard(days, log_file_id):
    # Get available log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    log_file_options = [{'label': 'All Log Files', 'value': 'all'}]
    log_file_options.extend([{'label': log['name'], 'value': log['id']} for log in log_files])
    
    # Get log data
    log_file_id_filter = None if log_file_id == 'all' else int(log_file_id)
    df = get_log_data(days=days, log_file_id=log_file_id_filter)
    
    # Handle empty data case
    if len(df) == 0:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            annotations=[{
                'text': 'No data available for the selected period',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }],
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            paper_bgcolor='white'
        )
        
        # Create empty stats table
        stats_table = html.Table([
            html.Thead(html.Tr([html.Th("Metric"), html.Th("Value")])),
            html.Tbody([
                html.Tr([html.Td("Total Visitors"), html.Td("0")]),
                html.Tr([html.Td("Conversion Rate"), html.Td("0%")]),
                html.Tr([html.Td("Top Converting Page"), html.Td("-")]),
                html.Tr([html.Td("Top Converting Country"), html.Td("-")])
            ])
        ], className="table table-striped")
        
        return (
            log_file_options,
            stats_table,
            empty_fig,
            empty_fig,
            empty_fig
        )
    
    # Define conversion pages (for this example, we'll consider specific pages as conversion pages)
    conversion_resources = [
        '/scheduledemo.php',
        '/contact.php',
        '/virtual-assistant.php'
    ]
    
    # Mark conversion pages
    df['is_conversion'] = df['resource'].apply(lambda x: any(conv in x.lower() for conv in conversion_resources))
    
    # Calculate conversion metrics
    total_visitors = df['ip_address'].nunique()
    converting_visitors = df[df['is_conversion']]['ip_address'].nunique()
    conversion_rate = (converting_visitors / total_visitors) * 100 if total_visitors > 0 else 0
    
    # Find top converting page
    if 'is_conversion' in df.columns and df['is_conversion'].any():
        conversion_pages = df[df['is_conversion']]['resource'].value_counts()
        top_page = conversion_pages.index[0] if not conversion_pages.empty else "-"
        top_page_count = conversion_pages.iloc[0] if not conversion_pages.empty else 0
    else:
        top_page = "-"
        top_page_count = 0
    
    # Find top converting country
    if 'is_conversion' in df.columns and df['is_conversion'].any() and 'country' in df.columns:
        conversion_countries = df[df['is_conversion']]['country'].value_counts()
        top_country = conversion_countries.index[0] if not conversion_countries.empty else "-"
        top_country_count = conversion_countries.iloc[0] if not conversion_countries.empty else 0
    else:
        top_country = "-"
        top_country_count = 0
    
    # Create stats table
    stats_table = html.Table([
        html.Thead(html.Tr([html.Th("Metric"), html.Th("Value")])),
        html.Tbody([
            html.Tr([html.Td("Total Visitors"), html.Td(f"{total_visitors:,}")]),
            html.Tr([html.Td("Converting Visitors"), html.Td(f"{converting_visitors:,}")]),
            html.Tr([html.Td("Conversion Rate"), html.Td(f"{conversion_rate:.2f}%")]),
            html.Tr([html.Td("Top Converting Page"), html.Td(f"{top_page} ({top_page_count:,} visits)")]),
            html.Tr([html.Td("Top Converting Country"), html.Td(f"{top_country} ({top_country_count:,} conversions)")])
        ])
    ], className="table table-striped", style={'width': '100%'})
    
    # Create conversion funnel
    funnel_data = [
        {'stage': 'Visitors', 'count': total_visitors},
        {'stage': 'Home Page', 'count': df[df['resource'].str.contains('/index.html', case=False)]['ip_address'].nunique()},
        {'stage': 'Product Pages', 'count': df[df['resource'].str.contains('/product|/prototype', case=False)]['ip_address'].nunique()},
        {'stage': 'Demo Request', 'count': df[df['resource'].str.contains('/scheduledemo.php', case=False)]['ip_address'].nunique()},
        {'stage': 'Contact', 'count': df[df['resource'].str.contains('/contact.php', case=False)]['ip_address'].nunique()}
    ]
    
    funnel_fig = go.Figure(go.Funnel(
        y=[stage['stage'] for stage in funnel_data],
        x=[stage['count'] for stage in funnel_data],
        textinfo="value+percent initial"
    ))
    
    funnel_fig.update_layout(
        title="Visitor Conversion Funnel",
        margin=dict(l=150, r=20, t=40, b=20),
        height=400,
        paper_bgcolor='white'
    )
    
    # Create conversion by country chart
    if 'country' in df.columns and 'is_conversion' in df.columns and df['is_conversion'].any():
        country_conversion = pd.crosstab(
            df['country'], 
            df['is_conversion'], 
            values=df['ip_address'], 
            aggfunc='nunique'
        ).reset_index()
        
        if not country_conversion.empty and country_conversion.shape[1] >= 3:
            country_conversion.columns = ['country', 'non_converting', 'converting']
            country_conversion.fillna(0, inplace=True)
            
            # Calculate conversion rate by country
            country_conversion['rate'] = (country_conversion['converting'] / 
                                         (country_conversion['converting'] + country_conversion['non_converting'])) * 100
            
            # Sort by conversion rate
            country_conversion = country_conversion.sort_values('rate', ascending=False).head(10)
            
            country_conv_fig = px.bar(
                country_conversion,
                y='country',
                x='rate',
                title='Conversion Rate by Country (Top 10)',
                labels={'rate': 'Conversion Rate (%)', 'country': 'Country'},
                orientation='h',
                color='rate',
                color_continuous_scale='Viridis',
                height=400
            )
            
            country_conv_fig.update_traces(
                texttemplate='%{x:.1f}%', 
                textposition='outside'
            )
            country_conv_fig.update_layout(
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
        else:
            # Fallback if the crosstab doesn't work as expected
            country_conv_fig = go.Figure()
            country_conv_fig.update_layout(
                title='Conversion Rate by Country',
                annotations=[{
                    'text': 'Insufficient conversion data by country',
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 20}
                }],
                height=400,
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor='white'
            )
    else:
        # Fallback empty country conversion chart
        country_conv_fig = go.Figure()
        country_conv_fig.update_layout(
            title='Conversion Rate by Country',
            annotations=[{
                'text': 'No conversion data by country available',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }],
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            paper_bgcolor='white'
        )
    
    # Conversion rate over time
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    
    # Group by date and calculate visitors and conversions
    daily_data = df.groupby('date').agg(
        visitors=('ip_address', 'nunique'),
        conversions=('is_conversion', 'sum')
    ).reset_index()
    
    daily_data['conversion_rate'] = (daily_data['conversions'] / daily_data['visitors']) * 100
    daily_data['conversion_rate'] = daily_data['conversion_rate'].fillna(0)
    
    time_series_fig = px.line(
        daily_data,
        x='date',
        y='conversion_rate',
        title='Daily Conversion Rate',
        labels={'conversion_rate': 'Conversion Rate (%)', 'date': 'Date'},
        height=400
    )
    
    time_series_fig.update_layout(
        yaxis=dict(ticksuffix='%'),
        hovermode='x',
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    return (
        log_file_options,
        stats_table,
        funnel_fig,
        country_conv_fig,
        time_series_fig
    )
    
    

# dashboard/dash_apps.py updated after meeting with client



# Create a Marketing Analytics Dashboard
marketing_app = DjangoDash('MarketingDashboard')

marketing_app.layout = html.Div([
    html.H1("Marketing Analytics Dashboard", className="text-center mb-4"),
    html.Div([
        html.Label("Select Date Range:"),
        dcc.Dropdown(
            id='marketing-date-range',
            options=[
                {'label': 'Last 7 Days', 'value': 7},
                {'label': 'Last 14 Days', 'value': 14},
                {'label': 'Last 30 Days', 'value': 30},
                {'label': 'Last 90 Days', 'value': 90},
                {'label': 'All Time', 'value': 3650},
            ],
            value=30,
            clearable=False,
            className="mb-4",
            style={'width': '300px'}
        ),
        html.Label("Select Log File (Optional):"),
        dcc.Dropdown(
            id='marketing-log-file-selector',
            options=[
                {'label': 'All Log Files', 'value': 'all'}
            ],
            value='all',
            clearable=False,
            className="mb-4",
            style={'width': '300px'}
        ),
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Key Performance Metrics", className="card-title"),
                html.Div(id="kpi-metrics", className="d-flex justify-content-between")
            ], className="card-body")
        ], className="card shadow-sm mb-4")
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Traffic Forecast (Next 7 Days)", className="card-title"),
                dcc.Graph(id="traffic-forecast-graph")
            ], className="card-body")
        ], className="card shadow-sm mb-4")
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("User Journey Analysis", className="card-title"),
                dcc.Graph(id="user-journey-graph")
            ], className="card-body")
        ], className="card shadow-sm mb-4")
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Traffic Distribution by Time", className="card-title"),
                dcc.Graph(id="traffic-time-heatmap")
            ], className="card-body")
        ], className="card shadow-sm mb-4", style={'width': '48%', 'display': 'inline-block', 'margin': '0 1%'}),
        
        html.Div([
            html.Div([
                html.H5("Conversion Path Analysis", className="card-title"),
                dcc.Graph(id="conversion-path-graph")
            ], className="card-body")
        ], className="card shadow-sm mb-4", style={'width': '48%', 'display': 'inline-block', 'margin': '0 1%'}),
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Customer Segmentation", className="card-title"),
                dcc.Graph(id="customer-segmentation-graph")
            ], className="card-body")
        ], className="card shadow-sm mb-4")
    ], className="mb-4 px-4"),
    
    html.Div([
        html.Div([
            html.Div([
                html.H5("Top Performing Pages & Bounce Rates", className="card-title"),
                dash_table.DataTable(
                    id='page-performance-table',
                    style_table={'overflowX': 'auto'},
                    style_cell={
                        'height': 'auto',
                        'minWidth': '150px', 'width': '150px', 'maxWidth': '200px',
                        'whiteSpace': 'normal'
                    },
                    style_header={
                        'backgroundColor': 'rgb(230, 230, 230)',
                        'fontWeight': 'bold'
                    },
                    page_current=0,
                    page_size=10,
                )
            ], className="card-body")
        ], className="card shadow-sm mb-4")
    ], className="mb-4 px-4"),
], style={'width': '100%', 'max-width': '100%', 'padding': '0', 'margin': '0'})

def get_enhanced_log_data(days=30, log_file_id=None):
    """
    Fetch log data from database with enhanced processing for marketing analytics
    
    Args:
        days: Number of days of data to fetch
        log_file_id: Optional specific log file ID to filter by
    
    Returns:
        Pandas DataFrame with enhanced log data
    """
    from django.utils import timezone
    from django.db.models import Count
    
    # Calculate date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Base queryset
    query = LogEntry.objects.filter(timestamp__gte=start_date)
    
    # Filter by log file if specified
    if log_file_id and log_file_id != 'all':
        query = query.filter(log_file_id=int(log_file_id))
    
    # Convert query to list of dictionaries
    data = list(query.values(
        'timestamp', 'ip_address', 'http_method', 
        'resource', 'status_code', 'country', 'page_category'
    ))
    
    # If no data, return empty DataFrame with expected columns
    if not data:
        return pd.DataFrame(columns=[
            'timestamp', 'ip_address', 'http_method', 
            'resource', 'status_code', 'country', 'page_category'
        ])
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Add derived fields to enhance analysis
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.day_name()
    
    # Define conversion pages
    conversion_resources = [
        '/scheduledemo.php',
        '/contact.php',
        '/virtual-assistant.php'
    ]
    
    # Mark conversion pages
    df['is_conversion'] = df['resource'].apply(lambda x: any(conv in x.lower() for conv in conversion_resources))
    
    # Calculate time spent by looking at timestamps for same IP address
    df = df.sort_values(['ip_address', 'timestamp'])
    
    # Calculate difference between current and next timestamp for same IP
    df['next_timestamp'] = df.groupby('ip_address')['timestamp'].shift(-1)
    df['time_spent'] = (df['next_timestamp'] - df['timestamp']).dt.total_seconds()
    
    # Clean up time spent (ignore page transitions > 30 minutes which likely indicate new session)
    df['time_spent'] = df['time_spent'].apply(lambda x: x if (x > 0 and x < 1800) else np.nan)
    
    # Define bounce (single page visit)
    df['session_id'] = df['ip_address'] + '_' + df['timestamp'].dt.strftime('%Y%m%d')
    df['is_bounce'] = df.groupby('session_id')['resource'].transform('count') == 1
    
    # Page entry/exit flags
    df['is_entry_page'] = ~df['session_id'].duplicated()
    df['is_exit_page'] = ~df['session_id'].duplicated(keep='last')
    
    return df

def forecast_traffic(df, days_to_forecast=7):
    """
    Generate traffic forecast based on historical data
    
    Args:
        df: DataFrame with log data
        days_to_forecast: Number of days to forecast
    
    Returns:
        DataFrame with actual and forecasted traffic
    """
    if len(df) == 0:
        return pd.DataFrame(columns=['date', 'actual', 'forecast', 'lower_bound', 'upper_bound'])
    
    # Aggregate traffic by date
    daily_traffic = df.groupby('date').size().reset_index(name='actual')
    daily_traffic['date'] = pd.to_datetime(daily_traffic['date'])
    
    # Create a continuous date range
    date_range = pd.date_range(
        start=daily_traffic['date'].min(),
        end=daily_traffic['date'].max(),
        freq='D'
    )
    
    # Create a complete DataFrame with potential missing dates
    complete_df = pd.DataFrame({'date': date_range})
    daily_traffic = pd.merge(complete_df, daily_traffic, on='date', how='left')
    daily_traffic['actual'] = daily_traffic['actual'].fillna(0)
    
    # If we have at least 7 days of data, use ARIMA model for forecasting
    if len(daily_traffic) >= 7:
        try:
            # Fit ARIMA model
            model = ARIMA(daily_traffic['actual'], order=(3,1,1))
            model_fit = model.fit()
            
            # Generate forecast
            forecast = model_fit.get_forecast(steps=days_to_forecast)
            forecast_values = forecast.predicted_mean
            ci = forecast.conf_int()
            
            # Create forecast DataFrame
            last_date = daily_traffic['date'].max()
            forecast_dates = pd.date_range(start=last_date + timedelta(days=1), periods=days_to_forecast, freq='D')
            
            forecast_df = pd.DataFrame({
                'date': forecast_dates,
                'actual': np.nan,
                'forecast': forecast_values.values,
                'lower_bound': ci.iloc[:, 0].values,
                'upper_bound': ci.iloc[:, 1].values
            })
            
            # Add forecast to historical data
            daily_traffic['forecast'] = np.nan
            daily_traffic['lower_bound'] = np.nan
            daily_traffic['upper_bound'] = np.nan
            
            result_df = pd.concat([daily_traffic, forecast_df], ignore_index=True)
            return result_df
            
        except Exception as e:
            # Fallback to simple linear regression if ARIMA fails
            print(f"ARIMA forecast failed: {str(e)}. Using simple trend instead.")
    
    # Simple trend forecasting (fallback)
    daily_traffic['day_number'] = range(len(daily_traffic))
    
    X = daily_traffic['day_number'].values.reshape(-1, 1)
    y = daily_traffic['actual'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Create forecast dates and day numbers
    last_date = daily_traffic['date'].max()
    forecast_dates = pd.date_range(start=last_date + timedelta(days=1), periods=days_to_forecast, freq='D')
    forecast_days = np.array(range(len(daily_traffic), len(daily_traffic) + days_to_forecast)).reshape(-1, 1)
    
    # Generate forecast
    forecast_values = model.predict(forecast_days)
    
    # Calculate confidence interval (simple approach)
    y_pred = model.predict(X)
    forecast_err = np.std(y - y_pred) * 1.96  # 95% confidence interval
    lower_bound = np.maximum(forecast_values - forecast_err, 0)  # Traffic can't be negative
    upper_bound = forecast_values + forecast_err
    
    # Create forecast DataFrame
    forecast_df = pd.DataFrame({
        'date': forecast_dates,
        'actual': np.nan,
        'forecast': forecast_values,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound
    })
    
    # Add forecast to historical data
    daily_traffic['forecast'] = np.nan
    daily_traffic['lower_bound'] = np.nan
    daily_traffic['upper_bound'] = np.nan
    
    result_df = pd.concat([daily_traffic, forecast_df], ignore_index=True)
    return result_df

def generate_user_journey(df):
    """
    Generate user journey sankey diagram data
    
    Args:
        df: DataFrame with log data
    
    Returns:
        Dictionary with sankey diagram data
    """
    if len(df) == 0:
        return None
    
    # Sort by session_id and timestamp
    journey_df = df.sort_values(['session_id', 'timestamp'])
    
    # Get transitions between pages
    journey_df['next_page'] = journey_df.groupby('session_id')['page_category'].shift(-1)
    
    # Filter out missing transitions (last page in session)
    transitions = journey_df.dropna(subset=['next_page'])
    
    # Count transitions
    transition_counts = transitions.groupby(['page_category', 'next_page']).size().reset_index(name='count')
    
    # Prepare sankey diagram data
    labels = list(set(transition_counts['page_category']).union(set(transition_counts['next_page'])))
    
    source = []
    target = []
    value = []
    
    label_to_idx = {label: idx for idx, label in enumerate(labels)}
    
    for _, row in transition_counts.iterrows():
        source.append(label_to_idx[row['page_category']])
        target.append(label_to_idx[row['next_page']])
        value.append(row['count'])
    
    return {
        'labels': labels,
        'source': source,
        'target': target,
        'value': value
    }

@marketing_app.callback(
    [Output('marketing-log-file-selector', 'options'),
     Output('kpi-metrics', 'children'),
     Output('traffic-forecast-graph', 'figure'),
     Output('user-journey-graph', 'figure'),
     Output('traffic-time-heatmap', 'figure'),
     Output('conversion-path-graph', 'figure'),
     Output('customer-segmentation-graph', 'figure'),
     Output('page-performance-table', 'data'),
     Output('page-performance-table', 'columns')],
    [Input('marketing-date-range', 'value'),
     Input('marketing-log-file-selector', 'value')]
)
def update_marketing_dashboard(days, log_file_id):
    # Get available log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    log_file_options = [{'label': 'All Log Files', 'value': 'all'}]
    log_file_options.extend([{'label': log['name'], 'value': log['id']} for log in log_files])
    
    # Get enhanced log data
    log_file_id_filter = None if log_file_id == 'all' else log_file_id
    df = get_enhanced_log_data(days=days, log_file_id=log_file_id_filter)
    
    # Handle empty data case
    if len(df) == 0:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            annotations=[{
                'text': 'No data available for the selected period',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }]
        )
        
        empty_kpi_metrics = [
            html.Div([
                html.Div("0", className="display-4"),
                html.Div("Total Sessions", className="text-muted")
            ], className="text-center mx-3"),
            html.Div([
                html.Div("0%", className="display-4"),
                html.Div("Conversion Rate", className="text-muted")
            ], className="text-center mx-3"),
            html.Div([
                html.Div("0%", className="display-4"),
                html.Div("Bounce Rate", className="text-muted")
            ], className="text-center mx-3"),
            html.Div([
                html.Div("0s", className="display-4"),
                html.Div("Avg. Time on Site", className="text-muted")
            ], className="text-center mx-3")
        ]
        
        empty_table_data = []
        empty_table_columns = [
            {"name": "Page", "id": "page"},
            {"name": "Views", "id": "views"},
            {"name": "Avg. Time (sec)", "id": "avg_time"},
            {"name": "Bounce Rate", "id": "bounce_rate"},
            {"name": "Conversion Rate", "id": "conversion_rate"}
        ]
        
        return (
            log_file_options,
            empty_kpi_metrics,
            empty_fig,
            empty_fig,
            empty_fig,
            empty_fig,
            empty_fig,
            empty_table_data,
            empty_table_columns
        )
    
    # 1. Calculate KPI metrics
    total_sessions = df['session_id'].nunique()
    conversion_rate = (df[df['is_conversion']]['session_id'].nunique() / total_sessions) * 100 if total_sessions > 0 else 0
    bounce_rate = (df[df['is_bounce']]['session_id'].nunique() / total_sessions) * 100 if total_sessions > 0 else 0
    avg_time_on_site = df.groupby('session_id')['time_spent'].sum().mean() or 0
    
    kpi_metrics = [
        html.Div([
            html.Div(f"{total_sessions:,}", className="display-4"),
            html.Div("Total Sessions", className="text-muted")
        ], className="text-center mx-3"),
        html.Div([
            html.Div(f"{conversion_rate:.1f}%", className="display-4"),
            html.Div("Conversion Rate", className="text-muted")
        ], className="text-center mx-3"),
        html.Div([
            html.Div(f"{bounce_rate:.1f}%", className="display-4"),
            html.Div("Bounce Rate", className="text-muted")
        ], className="text-center mx-3"),
        html.Div([
            html.Div(f"{avg_time_on_site:.1f}s", className="display-4"),
            html.Div("Avg. Time on Site", className="text-muted")
        ], className="text-center mx-3")
    ]
    
    # 2. Create traffic forecast
    forecast_data = forecast_traffic(df)
    
    forecast_fig = go.Figure()
    
    # Add actual traffic
    forecast_fig.add_trace(go.Scatter(
        x=forecast_data['date'],
        y=forecast_data['actual'],
        mode='lines+markers',
        name='Actual Traffic',
        line=dict(color='#0072B2', width=3),
        marker=dict(size=6)
    ))
    
    # Add forecast
    forecast_fig.add_trace(go.Scatter(
        x=forecast_data['date'],
        y=forecast_data['forecast'],
        mode='lines',
        name='Forecast',
        line=dict(color='#E69F00', width=3, dash='dash')
    ))
    
    # Add confidence interval
    forecast_fig.add_trace(go.Scatter(
        x=pd.concat([forecast_data['date'], forecast_data['date'].iloc[::-1]]),
        y=pd.concat([forecast_data['upper_bound'], forecast_data['lower_bound'].iloc[::-1]]),
        fill='toself',
        fillcolor='rgba(230, 159, 0, 0.2)',
        line=dict(color='rgba(255, 255, 255, 0)'),
        hoverinfo='skip',
        name='95% Confidence Interval'
    ))
    
    forecast_fig.update_layout(
        title='Traffic Forecast',
        xaxis_title='Date',
        yaxis_title='Visits',
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=20, t=60, b=40),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    # 3. Create user journey sankey diagram
    journey_data = generate_user_journey(df)
    
    if journey_data:
        journey_fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color='black', width=0.5),
                label=journey_data['labels'],
                color='#0072B2'
            ),
            link=dict(
                source=journey_data['source'],
                target=journey_data['target'],
                value=journey_data['value'],
                color='rgba(0, 114, 178, 0.3)'
            )
        )])
        
        journey_fig.update_layout(
            title='User Navigation Flow Between Page Categories',
            height=500,
            font=dict(size=12),
            margin=dict(l=20, r=20, t=60, b=20),
            paper_bgcolor='white'
        )
    else:
        journey_fig = go.Figure()
        journey_fig.update_layout(
            annotations=[{
                'text': 'Insufficient data for user journey analysis',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }],
            height=500,
            margin=dict(l=20, r=20, t=60, b=20),
            paper_bgcolor='white'
        )
    
    # 4. Create traffic heatmap by hour and day of week
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    traffic_by_time = df.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
    
    # Pivot for heatmap
    if not traffic_by_time.empty:
        pivot_data = traffic_by_time.pivot_table(index='day_of_week', columns='hour', values='count', fill_value=0)
        
        # Reorder days
        pivot_data = pivot_data.reindex(days_order)
        
        heatmap_fig = px.imshow(
            pivot_data,
            labels=dict(x="Hour of Day", y="Day of Week", color="Visits"),
            x=pivot_data.columns,
            y=pivot_data.index,
            color_continuous_scale='Blues',
            aspect="auto"
        )
        
        heatmap_fig.update_layout(
            title='Traffic Distribution by Day and Hour',
            xaxis_title='Hour of Day',
            yaxis_title='Day of Week',
            margin=dict(l=40, r=20, t=60, b=40),
            paper_bgcolor='white',
            height=400
        )
    else:
        heatmap_fig = go.Figure()
        heatmap_fig.update_layout(
            annotations=[{
                'text': 'Insufficient data for traffic heatmap',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }],
            height=400,
            margin=dict(l=20, r=20, t=60, b=20),
            paper_bgcolor='white'
        )
    
    # 5. Create conversion path analysis funnel
    # Identify common paths to conversion
    if df[df['is_conversion']].shape[0] > 0:
        # Get sessions with conversions
        conversion_sessions = df[df['is_conversion']]['session_id'].unique()
        
        # Get all entries from converting sessions
        conv_journey = df[df['session_id'].isin(conversion_sessions)].copy()
        
        # Mark pages that lead to conversion (pages viewed before conversion page)
        for session in conversion_sessions:
            session_data = conv_journey[conv_journey['session_id'] == session].sort_values('timestamp')
            conversion_idx = session_data[session_data['is_conversion']].index.min()
            if pd.notna(conversion_idx):
                conv_journey.loc[conv_journey['session_id'] == session, 'steps_to_conversion'] = -1
                steps = 0
                for idx in reversed(session_data.index):
                    if idx < conversion_idx:
                        conv_journey.loc[idx, 'steps_to_conversion'] = steps
                        steps += 1
        
        # Analyze pages by their position in the conversion path
        path_analysis = conv_journey.groupby(['page_category', 'steps_to_conversion']).size().reset_index(name='count')
        path_analysis = path_analysis[path_analysis['steps_to_conversion'] >= 0]
        
        if not path_analysis.empty:
            # Sort by steps to conversion
            path_analysis = path_analysis.sort_values('steps_to_conversion')
            
            # Get top categories at each step
            top_path_categories = []
            top_path_counts = []
            step_labels = []
            
            for step in sorted(path_analysis['steps_to_conversion'].unique()):
                step_data = path_analysis[path_analysis['steps_to_conversion'] == step]
                if not step_data.empty:
                    top_category = step_data.iloc[step_data['count'].argmax()]
                    top_path_categories.append(top_category['page_category'])
                    top_path_counts.append(top_category['count'])
                    step_labels.append(f"Step {int(step)}")
            
            conv_path_fig = go.Figure(go.Funnel(
                y=step_labels + ['Conversion'],
                x=top_path_counts + [df[df['is_conversion']].shape[0]],
                textinfo="value+percent initial",
                marker={"color": ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948']}
            ))
            
            conv_path_fig.update_layout(
                title='Path to Conversion',
                margin=dict(l=20, r=20, t=60, b=20),
                height=400,
                paper_bgcolor='white'
            )
        else:
            conv_path_fig = go.Figure()
            conv_path_fig.update_layout(
                annotations=[{
                    'text': 'Insufficient data for conversion path analysis',
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 20}
                }],
                height=400,
                margin=dict(l=20, r=20, t=60, b=20),
                paper_bgcolor='white'
            )
    else:
        conv_path_fig = go.Figure()
        conv_path_fig.update_layout(
            annotations=[{
                'text': 'No conversion data available',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }],
            height=400,
            margin=dict(l=20, r=20, t=60, b=20),
            paper_bgcolor='white'
        )
    
    # 6. Create customer segmentation by country and conversion behavior
    country_segments = df.groupby('country').agg(
        total_visits=('session_id', 'nunique'),
        avg_time=('time_spent', 'mean'),
        conversion_rate=('is_conversion', 'mean'),
        bounce_rate=('is_bounce', 'mean')
    ).reset_index()
    
    if not country_segments.empty:
        # Fill NaN values
        country_segments = country_segments.fillna(0)
        
        # Create scatterplot
        segment_fig = px.scatter(
            country_segments,
            x='avg_time',
            y='conversion_rate',
            size='total_visits',
            color='bounce_rate',
            hover_name='country',
            text='country',
            size_max=50,
            color_continuous_scale='RdYlGn_r',  # Red for high bounce, green for low bounce
            labels={
                'avg_time': 'Average Time on Site (seconds)',
                'conversion_rate': 'Conversion Rate',
                'total_visits': 'Total Sessions',
                'bounce_rate': 'Bounce Rate'
            }
        )
        
        segment_fig.update_traces(
            textposition='top center',
            marker=dict(line=dict(width=1, color='DarkSlateGrey'))
        )
        
        segment_fig.update_layout(
            title='Customer Segmentation by Country',
            xaxis_title='Average Time on Site (seconds)',
            yaxis_title='Conversion Rate',
            height=500,
            margin=dict(l=40, r=20, t=60, b=40),
            paper_bgcolor='white',
            plot_bgcolor='white',
            coloraxis_colorbar=dict(
                title='Bounce Rate',
                tickformat=',.0%'
            )
        )
    else:
        segment_fig = go.Figure()
        segment_fig.update_layout(
            annotations=[{
                'text': 'Insufficient data for customer segmentation',
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 20}
            }],
            height=500,
            margin=dict(l=20, r=20, t=60, b=20),
            paper_bgcolor='white'
        )
    
    # 7. Create top performing pages table
    page_performance = df.groupby('resource').agg(
        views=('resource', 'count'),
        avg_time=('time_spent', 'mean'),
        bounce_rate=('is_bounce', 'mean'),
        conversion_rate=('is_conversion', 'mean'),
        entry_count=('is_entry_page', 'sum')
    ).reset_index()
    
    # Sort by most viewed pages
    page_performance = page_performance.sort_values('views', ascending=False).head(20)
    
    # Format for data table
    page_table_data = []
    for _, row in page_performance.iterrows():
        page_table_data.append({
            'page': row['resource'],
            'views': f"{int(row['views']):,}",
            'avg_time': f"{row['avg_time']:.1f}" if pd.notna(row['avg_time']) else "0.0",
            'bounce_rate': f"{row['bounce_rate']*100:.1f}%" if pd.notna(row['bounce_rate']) else "0.0%",
            'conversion_rate': f"{row['conversion_rate']*100:.1f}%" if pd.notna(row['conversion_rate']) else "0.0%",
            'entries': f"{int(row['entry_count']):,}" if pd.notna(row['entry_count']) else "0"
        })
    
    page_table_columns = [
        {"name": "Page", "id": "page"},
        {"name": "Views", "id": "views"},
        {"name": "Avg. Time (sec)", "id": "avg_time"},
        {"name": "Bounce Rate", "id": "bounce_rate"},
        {"name": "Conversion Rate", "id": "conversion_rate"},
        {"name": "Entries", "id": "entries"}
    ]
    
    return (
        log_file_options,
        kpi_metrics,
        forecast_fig,
        journey_fig,
        heatmap_fig,
        conv_path_fig,
        segment_fig,
        page_table_data,
        page_table_columns
    )