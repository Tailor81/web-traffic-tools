# dashboard/dash_apps.py
from django_plotly_dash import DjangoDash
from dash import dcc, html, Input, Output, callback_context
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import models from log_analyzer app
from log_analyzer.models import LogFile, LogEntry

# Function to fetch log data from database
def get_log_data(days=30, log_file_id=None):
    """Fetch log data with caching"""
    from django.utils import timezone
    from django.core.cache import cache
    from django.conf import settings
    
    cache_key = f'log_data_{days}_{log_file_id}'
    cached_data = cache.get(cache_key)
    
    if cached_data is not None:
        return cached_data
    
    # Get base queryset with select_related for better performance
    base_queryset = LogEntry.objects.select_related('log_file')
    
    # Filter by log file if specified
    if log_file_id:
        base_queryset = base_queryset.filter(log_file_id=log_file_id)
    
    # Get data for the specified date range
    start_date = timezone.now() - timedelta(days=days)
    data = list(base_queryset.filter(timestamp__gte=start_date).values(
        'timestamp', 'ip_address', 'http_method', 'resource', 
        'status_code', 'country', 'page_category', 'user_agent',
        'referer', 'session_id', 'response_time_ms', 'bytes_sent'
    ))
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Ensure timestamp is datetime
    if not df.empty and 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Fill NaN values with appropriate defaults
    if not df.empty:
        df['country'] = df['country'].fillna('Unknown')
        df['page_category'] = df['page_category'].fillna('other')
        df['user_agent'] = df['user_agent'].fillna('')
        df['referer'] = df['referer'].fillna('')
        df['session_id'] = df['session_id'].fillna('')
        df['response_time_ms'] = df['response_time_ms'].fillna(0)
        df['bytes_sent'] = df['bytes_sent'].fillna(0)
        df['status_code'] = df['status_code'].fillna(200)
        df['http_method'] = df['http_method'].fillna('GET')
        df['resource'] = df['resource'].fillna('/')
    
    # Cache the data for 1 minute
    cache.set(cache_key, df, 60)
    
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
        # Add real-time toggle
        html.Div([
            html.Label("Real-time Updates:"),
            dcc.Checklist(
                id='real-time-toggle',
                options=[{'label': 'Enable Real-time Updates', 'value': 'enabled'}],
                value=['enabled'],
                className="mb-4"
            )
        ])
    ], className="mb-4 px-4"),
    
    # Add interval component for real-time updates
    dcc.Interval(
        id='interval-component',
        interval=2*1000,  # 2 seconds
        n_intervals=0,
        disabled=False
    ),
    
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
    [Output('interval-component', 'disabled'),
     Output('interval-component', 'interval')],
    [Input('real-time-toggle', 'value')]
)
def toggle_real_time(real_time_enabled):
    if 'enabled' in real_time_enabled:
        return False, 2*1000  # 2 seconds
    return True, 5*60*1000  # 5 minutes

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
     Input('log-file-selector', 'value'),
     Input('interval-component', 'n_intervals')]
)
def update_traffic_dashboard(days, log_file_id, n_intervals):
    """Update traffic dashboard with real-time data"""
    try:
        # Get available log files for dropdown
        log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
        log_file_options = [{'label': 'All Log Files', 'value': 'all'}]
        log_file_options.extend([{'label': log['name'], 'value': log['id']} for log in log_files])
        
        # Get log data with caching for better performance
        log_file_id_filter = None if log_file_id == 'all' else int(log_file_id)
        df = get_log_data(days=days, log_file_id=log_file_id_filter)
        
        # Handle empty data case
        if df.empty:
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
        
        # Calculate metrics with proper handling of empty data
        total_visits = len(df)
        unique_visitors = df['ip_address'].nunique()
        success_count = len(df[df['status_code'].between(200, 299)])
        error_count = len(df[df['status_code'].between(400, 599)])

        success_rate = (success_count / total_visits * 100) if total_visits > 0 else 0
        error_rate = (error_count / total_visits * 100) if total_visits > 0 else 0
        
        # Traffic over time graph with real-time updates
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        daily_traffic = df.groupby('date').size().reset_index(name='count')
        time_fig = px.line(
            daily_traffic, 
            x='date', 
            y='count',
            title='Daily Traffic',
            labels={'count': 'Visits', 'date': 'Date'},
            height=400
        )
        time_fig.update_layout(
            hovermode='x',
            margin=dict(l=20, r=20, t=40, b=20),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        
        # Page categories pie chart with real-time updates
        category_counts = df['page_category'].value_counts().reset_index()
        category_counts.columns = ['category', 'count']
        category_fig = px.pie(
            category_counts,
            values='count',
            names='category',
            title='Traffic by Page Category',
            height=400
        )
        category_fig.update_traces(textposition='inside', textinfo='percent+label')
        
        # Status codes bar chart with real-time updates
        status_counts = df['status_code'].value_counts().reset_index()
        status_counts.columns = ['status', 'count']
        status_fig = px.bar(
            status_counts,
            x='status',
            y='count',
            title='HTTP Status Codes',
            height=400
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
        
    except Exception as e:
        logger.error(f"Error updating traffic dashboard: {e}")
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
        # Add real-time toggle
        html.Div([
            html.Label("Real-time Updates:"),
            dcc.Checklist(
                id='geo-real-time-toggle',
                options=[{'label': 'Enable Real-time Updates', 'value': 'enabled'}],
                value=['enabled'],
                className="mb-4"
            )
        ])
    ], className="mb-4 px-4"),
    
    # Add interval component for real-time updates
    dcc.Interval(
        id='geo-interval-component',
        interval=2*1000,  # 2 seconds
        n_intervals=0,
        disabled=False
    ),
    
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
    [Output('geo-interval-component', 'disabled'),
     Output('geo-interval-component', 'interval')],
    [Input('geo-real-time-toggle', 'value')]
)
def toggle_geo_real_time(real_time_enabled):
    if 'enabled' in real_time_enabled:
        return False, 2*1000  # 2 seconds
    return True, 5*60*1000  # 5 minutes

@geo_app.callback(
    [Output('geo-log-file-selector', 'options'),
     Output('country-bar-chart', 'figure'),
     Output('country-map', 'figure'),
     Output('country-category-heatmap', 'figure')],
    [Input('geo-date-range', 'value'),
     Input('geo-log-file-selector', 'value'),
     Input('geo-interval-component', 'n_intervals')]
)
def update_geo_dashboard(days, log_file_id, n_intervals):
    # Get available log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    log_file_options = [{'label': 'All Log Files', 'value': 'all'}]
    log_file_options.extend([{'label': log['name'], 'value': log['id']} for log in log_files])
    
    # Get log data with caching
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
    
    # Country bar chart with real-time updates
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
    
    # Country map with real-time updates
    country_map_fig = px.choropleth(
        country_counts,
        locations='country',
        locationmode='country names',
        color='count',
        color_continuous_scale='Blues',
        title='Traffic Distribution by Country',
        height=500
    )
    country_map_fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    # Country-category heatmap with real-time updates
    country_category_data = []
    top_countries = country_counts['country'].tolist()
    
    for country in top_countries:
        category_data = df[df['country'] == country]['page_category'].value_counts()
        for category, count in category_data.items():
            country_category_data.append({
                'country': country,
                'category': category,
                'count': count
            })
    
    heatmap_fig = px.density_heatmap(
        pd.DataFrame(country_category_data),
        x='country',
        y='category',
        z='count',
        title='Traffic by Country and Page Category',
        height=500
    )
    heatmap_fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
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
        # Add real-time toggle
        html.Div([
            html.Label("Real-time Updates:"),
            dcc.Checklist(
                id='conv-real-time-toggle',
                options=[{'label': 'Enable Real-time Updates', 'value': 'enabled'}],
                value=['enabled'],
                className="mb-4"
            )
        ])
    ], className="mb-4 px-4"),
    
    # Add interval component for real-time updates
    dcc.Interval(
        id='conv-interval-component',
        interval=2*1000,  # 2 seconds
        n_intervals=0,
        disabled=False
    ),
    
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
    [Output('conv-interval-component', 'disabled'),
     Output('conv-interval-component', 'interval')],
    [Input('conv-real-time-toggle', 'value')]
)
def toggle_conv_real_time(real_time_enabled):
    if 'enabled' in real_time_enabled:
        return False, 2*1000  # 2 seconds
    return True, 5*60*1000  # 5 minutes

@conversion_app.callback(
    [Output('conv-log-file-selector', 'options'),
     Output('conversion-stats', 'children'),
     Output('conversion-funnel', 'figure'),
     Output('conversion-by-country', 'figure'),
     Output('conversion-time-series', 'figure')],
    [Input('conv-date-range', 'value'),
     Input('conv-log-file-selector', 'value'),
     Input('conv-interval-component', 'n_intervals')]
)
def update_conversion_dashboard(days, log_file_id, n_intervals):
    # Get available log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    log_file_options = [{'label': 'All Log Files', 'value': 'all'}]
    log_file_options.extend([{'label': log['name'], 'value': log['id']} for log in log_files])
    
    # Get log data with caching
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
    
    # Define conversion pages
    conversion_resources = [
        '/scheduledemo.php',
        '/contact.php',
        '/virtual-assistant.php'
    ]
    
    # Mark conversion pages
    df['is_conversion'] = df['resource'].apply(lambda x: any(conv in x.lower() for conv in conversion_resources))
    
    # Calculate conversion metrics with real-time updates
    total_visitors = df['ip_address'].nunique()
    converting_visitors = df[
        (df['resource'].str.contains('scheduledemo|contact|signup', case=False, na=False)) |
        (df['status_code'].between(200, 299))
    ]['ip_address'].nunique()

    conversion_rate = (converting_visitors / total_visitors * 100) if total_visitors > 0 else 0
    
    # Get top converting page
    conversion_by_page = df[df['is_conversion']]['resource'].value_counts()
    top_converting_page = conversion_by_page.index[0] if not conversion_by_page.empty else "-"
    
    # Get top converting country
    conversion_by_country = df[df['is_conversion']]['country'].value_counts()
    top_converting_country = conversion_by_country.index[0] if not conversion_by_country.empty else "-"
    
    # Create stats table with real-time updates
    stats_table = html.Table([
        html.Thead(html.Tr([html.Th("Metric"), html.Th("Value")])),
        html.Tbody([
            html.Tr([html.Td("Total Visitors"), html.Td(f"{total_visitors:,}")]),
            html.Tr([html.Td("Conversion Rate"), html.Td(f"{conversion_rate:.1f}%")]),
            html.Tr([html.Td("Top Converting Page"), html.Td(top_converting_page)]),
            html.Tr([html.Td("Top Converting Country"), html.Td(top_converting_country)])
        ])
    ], className="table table-striped")
    
    # Conversion funnel with real-time updates
    funnel_data = []
    for resource in conversion_resources:
        count = len(df[df['resource'].str.contains(resource, case=False)])
        funnel_data.append({
            'page': resource,
            'visitors': count
        })
    
    funnel_fig = px.funnel(
        pd.DataFrame(funnel_data),
        x='visitors',
        y='page',
        title='Conversion Funnel',
        height=400
    )
    funnel_fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    # Conversion by country with real-time updates
    country_data = df[df['is_conversion']]['country'].value_counts().reset_index()
    country_data.columns = ['country', 'conversions']
    country_fig = px.bar(
        country_data.head(10),
        x='country',
        y='conversions',
        title='Top 10 Countries by Conversions',
        height=400
    )
    country_fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    # Conversion time series with real-time updates
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily_data = df.groupby('date').size().reset_index(name='total')
    conversion_daily = df[df['is_conversion']].groupby('date').size().reset_index(name='conversions')
    
    time_series_data = pd.merge(daily_data, conversion_daily, on='date', how='left')
    time_series_data['conversions'] = time_series_data['conversions'].fillna(0)
    time_series_data['conversion_rate'] = time_series_data.apply(
        lambda row: (row['conversions'] / row['total'] * 100) if row['total'] > 0 else 0,
        axis=1
    )
    
    time_series_fig = px.line(
        time_series_data,
        x='date',
        y='conversion_rate',
        title='Conversion Rate Over Time',
        height=400
    )
    time_series_fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
        plot_bgcolor='white'
    )
    
    return (
        log_file_options,
        stats_table,
        funnel_fig,
        country_fig,
        time_series_fig
    )