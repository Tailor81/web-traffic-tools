import os
import csv
import json
from io import StringIO, BytesIO
from datetime import datetime
from django.http import HttpResponse
from django.template.loader import render_to_string
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from log_analyzer.models import LogEntry

def generate_summary_report(report):
    """Generate a summary report based on log data"""
    log_file = report.log_file
    entries = LogEntry.objects.filter(log_file=log_file)
    
    # Convert to pandas DataFrame
    entry_dicts = []
    for entry in entries:
        entry_dicts.append({
            'timestamp': entry.timestamp,
            'ip_address': entry.ip_address,
            'http_method': entry.http_method,
            'resource': entry.resource,
            'status_code': entry.status_code,
            'country': entry.country,
            'page_category': entry.page_category
        })
    
    df = pd.DataFrame(entry_dicts)
    
    # Generate report based on format
    if report.format == 'csv':
        return generate_csv_report(df, report)
    elif report.format == 'excel':
        return generate_excel_report(df, report)
    elif report.format == 'pdf':
        return generate_pdf_report(df, report)
    
    return None

def generate_csv_report(df, report):
    """Generate a CSV report from DataFrame"""
    output = StringIO()
    
    # Write summary statistics
    writer = csv.writer(output)
    writer.writerow(['Summary Report', report.name])
    writer.writerow(['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow(['Log File', report.log_file.name])
    writer.writerow(['Total Entries', len(df)])
    writer.writerow([])
    
    # Write status code counts
    writer.writerow(['Status Code Distribution'])
    status_counts = df['status_code'].value_counts().reset_index()
    status_counts.columns = ['Status Code', 'Count']
    for _, row in status_counts.iterrows():
        writer.writerow([row['Status Code'], row['Count']])
    writer.writerow([])
    
    # Write country distribution
    writer.writerow(['Country Distribution'])
    country_counts = df['country'].value_counts().reset_index()
    country_counts.columns = ['Country', 'Count']
    for _, row in country_counts.iterrows():
        writer.writerow([row['Country'], row['Count']])
    writer.writerow([])
    
    # Write page category distribution
    writer.writerow(['Page Category Distribution'])
    category_counts = df['page_category'].value_counts().reset_index()
    category_counts.columns = ['Category', 'Count']
    for _, row in category_counts.iterrows():
        writer.writerow([row['Category'], row['Count']])
    
    # Save the report
    filename = f"{report.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    report.file.save(filename, ContentFile(output.getvalue().encode('utf-8')))
    
    return report.file.path

def generate_excel_report(df, report):
    """Generate an Excel report from DataFrame"""
    output = BytesIO()
    
    # Create Excel writer
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # Write summary sheet
    summary_data = {
        'Metric': ['Total Entries', 'Unique IP Addresses', 'Success Responses (200)', 'Error Responses (4xx, 5xx)'],
        'Value': [
            len(df),
            df['ip_address'].nunique(),
            len(df[df['status_code'] == 200]),
            len(df[(df['status_code'] >= 400) & (df['status_code'] < 600)])
        ]
    }
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    # Write status distribution sheet
    status_counts = df['status_code'].value_counts().reset_index()
    status_counts.columns = ['Status Code', 'Count']
    status_counts.to_excel(writer, sheet_name='Status Codes', index=False)
    
    # Write country distribution sheet
    country_counts = df['country'].value_counts().reset_index()
    country_counts.columns = ['Country', 'Count']
    country_counts.to_excel(writer, sheet_name='Countries', index=False)
    
    # Write category distribution sheet
    category_counts = df['page_category'].value_counts().reset_index()
    category_counts.columns = ['Category', 'Count']
    category_counts.to_excel(writer, sheet_name='Categories', index=False)
    
    # Write raw data sheet
    df.to_excel(writer, sheet_name='Raw Data', index=False)
    
    writer.close()
    
    # Save the report
    filename = f"{report.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    from django.core.files.base import ContentFile
    report.file.save(filename, ContentFile(output.getvalue()))
    
    return report.file.path

def generate_pdf_report(df, report):
    """Generate a PDF report with visualizations"""
    # Create a BytesIO object
    output = BytesIO()
    
    # Create PdfPages object
    with PdfPages(output) as pdf:
        # Create summary page
        plt.figure(figsize=(10, 6))
        plt.axis('off')
        plt.text(0.5, 0.95, f"Summary Report: {report.name}", ha='center', fontsize=16, fontweight='bold')
        plt.text(0.5, 0.9, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ha='center', fontsize=12)
        plt.text(0.5, 0.85, f"Log File: {report.log_file.name}", ha='center', fontsize=12)
        plt.text(0.5, 0.8, f"Total Entries: {len(df)}", ha='center', fontsize=12)
        plt.text(0.5, 0.75, f"Unique IP Addresses: {df['ip_address'].nunique()}", ha='center', fontsize=12)
        plt.text(0.5, 0.7, f"Success Responses (200): {len(df[df['status_code'] == 200])}", ha='center', fontsize=12)
        plt.text(0.5, 0.65, f"Error Responses (4xx, 5xx): {len(df[(df['status_code'] >= 400) & (df['status_code'] < 600)])}", ha='center', fontsize=12)
        
        pdf.savefig()
        plt.close()
        
        # Create status code distribution page
        plt.figure(figsize=(10, 6))
        status_counts = df['status_code'].value_counts()
        status_counts.plot(kind='bar')
        plt.title('Status Code Distribution')
        plt.ylabel('Count')
        plt.xlabel('Status Code')
        plt.tight_layout()
        
        pdf.savefig()
        plt.close()
        
        # Create country distribution page
        plt.figure(figsize=(10, 6))
        country_counts = df['country'].value_counts().head(10)  # Top 10 countries
        country_counts.plot(kind='barh')
        plt.title('Top 10 Countries')
        plt.xlabel('Count')
        plt.tight_layout()
        
        pdf.savefig()
        plt.close()
        
        # Create page category distribution page
        plt.figure(figsize=(10, 6))
        category_counts = df['page_category'].value_counts()
        plt.pie(category_counts, labels=category_counts.index, autopct='%1.1f%%')
        plt.title('Page Category Distribution')
        plt.axis('equal')
        
        pdf.savefig()
        plt.close()
    
    # Save the report
    filename = f"{report.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    from django.core.files.base import ContentFile
    report.file.save(filename, ContentFile(output.getvalue()))
    
    return report.file.path