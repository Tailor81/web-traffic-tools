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