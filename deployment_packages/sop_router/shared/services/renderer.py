"""
Certificate rendering service with HTML sanitization and PDF generation.
"""

import asyncio
import logging
import os
import re
from typing import Optional, Dict, Any
import requests
from jinja2 import Environment, BaseLoader, select_autoescape
from jinja2.exceptions import TemplateError
from bs4 import BeautifulSoup

from ..models import CertificateContext, PDFGenerationRequest, PDFGenerationResponse

logger = logging.getLogger(__name__)


class CertificateRenderer:
    """Certificate rendering service with HTML sanitization and PDF generation."""

    def __init__(self, html_to_pdf_api_url: Optional[str] = None):
        """Initialize certificate renderer."""
        self.html_to_pdf_api_url = html_to_pdf_api_url
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.jinja_env.filters['date_format'] = self._date_format_filter
        self.jinja_env.filters['safe_html'] = self._safe_html_filter

    def _date_format_filter(self, date_str: str, format_str: str = '%B %d, %Y') -> str:
        """Custom date formatting filter."""
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime(format_str)
        except:
            return date_str

    def _safe_html_filter(self, html: str) -> str:
        """Safe HTML filter that allows basic formatting."""
        # Allow only safe HTML tags
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span']
        soup = BeautifulSoup(html, 'html.parser')
        
        for tag in soup.find_all():
            if tag.name not in allowed_tags:
                tag.unwrap()
        
        return str(soup)

    def sanitize_template(self, html_template: str) -> str:
        """
        Sanitize HTML template to prevent XSS and remote resource loading.
        """
        try:
            soup = BeautifulSoup(html_template, 'html.parser')
            
            # Remove script tags
            for script in soup.find_all('script'):
                script.decompose()
            
            # Remove style tags with external resources
            for style in soup.find_all('style'):
                if 'url(' in style.string or '@import' in style.string:
                    style.decompose()
            
            # Remove link tags with external resources
            for link in soup.find_all('link'):
                href = link.get('href', '')
                if href.startswith('http://') or href.startswith('https://'):
                    link.decompose()
            
            # Remove img tags with external sources
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if src.startswith('http://') or src.startswith('https://'):
                    img.decompose()
            
            # Remove any remaining external resource references
            html_content = str(soup)
            
            # Remove external CSS imports
            html_content = re.sub(r'@import\s+url\([^)]+\);', '', html_content)
            
            # Remove external font imports
            html_content = re.sub(r'@font-face\s*{[^}]*url\([^)]+\)[^}]*}', '', html_content, flags=re.DOTALL)
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error sanitizing template: {e}")
            return html_template

    def render_certificate(self, template_html: str, context: CertificateContext) -> str:
        """
        Render certificate HTML using Jinja2 template.
        """
        try:
            # Sanitize template first
            #sanitized_template = self.sanitize_template(template_html)
            
            # Create template
            template = self.jinja_env.from_string(template_html)

            # Convert date format
            iso_date_str = str(context.completion_date)
            formatted_date = self._date_format_filter(iso_date_str, "%B %d, %Y")

            # Prepare context data with both formats (curly braces and underscores)
            context_data = {
                # Underscore format (Jinja2 style)
                'learner_name': context.learner_name,
                'course_name': context.course_name,
                'completion_date': formatted_date,
                'organization': context.organization,
                'learner_email': context.learner_email,
                'custom_fields': context.custom_fields or {},
                
                # Curly brace format (simple replacement)
                'learnerName': context.learner_name,
                'courseName': context.course_name,
                'completionDate': formatted_date,
                'organizationName': context.organization,
                'learnerEmail': context.learner_email
            }
            
            # Add any custom fields to the root context
            if context.custom_fields:
                context_data.update(context.custom_fields)
            
            # Render template
            rendered_html = template.render(**context_data)
            
            # Also handle simple curly brace replacement for templates that don't use Jinja2
            rendered_html = rendered_html.replace('{learnerName}', context.learner_name)
            rendered_html = rendered_html.replace('{courseName}', context.course_name)
            rendered_html = rendered_html.replace('{completionDate}', formatted_date)
            rendered_html = rendered_html.replace('{organizationName}', context.organization)
            rendered_html = rendered_html.replace('{learnerEmail}', context.learner_email)
            
            # Post-process to ensure valid HTML
            rendered_html = self._ensure_valid_html(rendered_html)
            
            return rendered_html
            
        except TemplateError as e:
            logger.error(f"Template rendering error: {e}")
            raise ValueError(f"Template rendering failed: {str(e)}")
        except Exception as e:
            logger.error(f"Error rendering certificate: {e}")
            raise ValueError(f"Certificate rendering failed: {str(e)}")

    def _ensure_valid_html(self, html: str) -> str:
        """Ensure the HTML is valid and complete."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # If no html tag, wrap in basic HTML structure
            if not soup.find('html'):
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Certificate</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            margin: 0;
                            padding: 20px;
                            background-color: #f5f5f5;
                        }}
                        .certificate {{
                            max-width: 800px;
                            margin: 0 auto;
                            background-color: white;
                            padding: 40px;
                            border-radius: 10px;
                            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                        }}
                    </style>
                </head>
                <body>
                    <div class="certificate">
                        {html}
                    </div>
                </body>
                </html>
                """
                return html_content
            
            return str(soup)
            
        except Exception as e:
            logger.error(f"Error ensuring valid HTML: {e}")
            return html


    def html_to_pdf_external_api(self, html_content: str, filename: str) -> Optional[bytes]:
        """
        Convert HTML to PDF using external API service.
        """
        try:
            if not self.html_to_pdf_api_url:
                return None
            
            # Prepare request data
            data = {
                'html': html_content,
                'filename': filename,
                'options': {
                    'format': 'A4',
                    'margin': {
                        'top': '20mm',
                        'right': '20mm',
                        'bottom': '20mm',
                        'left': '20mm'
                    },
                    'printBackground': True
                }
            }
            
            # Make request
            response = requests.post(
                self.html_to_pdf_api_url,
                json=data,
                timeout=60,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"External PDF API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling external PDF API: {e}")
            return None

    def html_to_pdf(self, html_content: str, filename: str) -> PDFGenerationResponse:
        """
        Convert HTML to PDF using PDFEndpoint API.
        """
        try:
            logger.info("Generating PDF using PDFEndpoint API")
            pdf_result = self._generate_pdf_with_pdfendpoint(html_content, filename)
            
            if pdf_result['success']:
                logger.info(f"PDF generated successfully: {pdf_result['data']['file_size']} bytes")
                return PDFGenerationResponse(ok=True, file_id="pdf_generated")
            else:
                logger.error(f"PDFEndpoint API failed: {pdf_result.get('error', 'Unknown error')}")
                return PDFGenerationResponse(ok=False, error="PDF generation failed")
            
        except Exception as e:
            logger.error(f"Error in html_to_pdf: {e}")
            return PDFGenerationResponse(
                ok=False,
                error=f"PDF generation error: {str(e)}"
            )

    def get_pdf_bytes(self, html_content: str, context: CertificateContext) -> Optional[bytes]:
        """
        Generate PDF bytes directly from HTML content.
        Primary method: WeasyPrint
        Fallback method: PDFEndpoint API
        """
        try:
            # Render HTML with context (this handles all dynamic value logic)
            rendered_html = self.render_certificate(html_content, context)
            
            # # Try WeasyPrint first (primary method)
            # pdf_bytes = self._generate_pdf_with_weasyprint(rendered_html)
            # if pdf_bytes:
            #     logger.info(f"PDF generated successfully using WeasyPrint: {len(pdf_bytes)} bytes")
            #     return pdf_bytes
            
            # Fallback to PDFEndpoint API if WeasyPrint fails
            logger.info("WeasyPrint failed, falling back to PDFEndpoint API")
            pdf_result = self._generate_pdf_with_pdfendpoint(rendered_html, "certificate.pdf")
            
            if pdf_result['success']:
                # Download the PDF from the URL
                pdf_url = pdf_result['data']['url']
                logger.info(f"Downloading PDF from URL: {pdf_url}")
                
                response = requests.get(pdf_url, timeout=30)
                if response.status_code == 200:
                    pdf_bytes = response.content
                    logger.info(f"Downloaded PDF: {len(pdf_bytes)} bytes")
                    return pdf_bytes
                else:
                    logger.error(f"Failed to download PDF: HTTP {response.status_code}")
                    return None
            else:
                logger.error(f"PDFEndpoint API failed: {pdf_result.get('error', 'Unknown error')}")
                return None
            
        except Exception as e:
            logger.error(f"Error generating PDF bytes: {e}")
            return None

    def _generate_pdf_with_weasyprint(self, html_filled: str) -> Optional[bytes]:
        """
        Generate PDF using WeasyPrint library.
        Returns PDF bytes if successful, None otherwise.
        """
        try:
            from weasyprint import HTML, CSS
            from io import BytesIO
            
            logger.info("Generating PDF using WeasyPrint")
            
            # CSS to scale the HTML to fit A3 page (as per user's requirement)
            scaling_css = CSS(string="""
                @page {
                    size: A3;
                    margin: 0;
                }
            """)
            
            # Generate PDF to bytes buffer
            pdf_buffer = BytesIO()
            HTML(string=html_filled).write_pdf(pdf_buffer, stylesheets=[scaling_css])
            pdf_bytes = pdf_buffer.getvalue()
            pdf_buffer.close()
            
            if pdf_bytes and len(pdf_bytes) > 0:
                logger.info(f"WeasyPrint generated PDF: {len(pdf_bytes)} bytes")
                return pdf_bytes
            else:
                logger.warning("WeasyPrint generated empty PDF")
                return None
                
        except ImportError:
            logger.warning("WeasyPrint not available, will use fallback method")
            return None
        except Exception as e:
            logger.error(f"WeasyPrint PDF generation error: {e}")
            return None

    def _generate_pdf_with_pdfendpoint(self, html_content: str, filename: str) -> dict:
        """
        Generate PDF using PDFEndpoint API with full CSS support.
        This is the production method that properly handles CSS styling.
        """
        try:
            import json
            
            logger.info("Starting PDFEndpoint PDF generation")
            
            # PDFEndpoint API configuration with multiple keys for fallback
            api_url = "https://api.pdfendpoint.com/v1/convert"
            api_tokens = [
                "pdfe_live_302b2ea1dbb69eda24f127988523a36a0a4d",
                "pdfe_live_caf821c185031e38be28a9479aff57b22471",
                "pdfe_live_c249d6190e000d6e3d2da7c84f44f136ee7a",
                "pdfe_live_8c47e634349a3b9e59185d17b5c3d4459fa9"
            ]
            
            # Prepare payload
            payload = {
                "html": html_content,
                "sandbox": False,
                "orientation": "horizontal",
                "page_size": "A4"
            }
            
            logger.info(f"Sending request to PDFEndpoint API: {len(html_content)} characters")
            
            # Try each API token until one succeeds
            last_error = None
            for i, api_token in enumerate(api_tokens):
                try:
                    logger.info(f"Trying API token {i+1}/{len(api_tokens)}")
                    
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_token}"
                    }
                    
                    # Make API request
                    response = requests.post(api_url, json=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"PDFEndpoint API response: {result}")
                        
                        if result.get('success', False):
                            logger.info(f"PDF generated successfully with token {i+1}: {result['data']['file_size']} bytes")
                            return {
                                'success': True,
                                'data': result['data']
                            }
                        else:
                            logger.warning(f"PDFEndpoint API token {i+1} returned success=false: {result}")
                            last_error = result.get('error', 'Unknown error')
                            continue  # Try next token
                    else:
                        logger.warning(f"PDFEndpoint API token {i+1} failed with status {response.status_code}: {response.text}")
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        continue  # Try next token
                        
                except Exception as e:
                    logger.warning(f"PDFEndpoint API token {i+1} failed with exception: {e}")
                    last_error = str(e)
                    continue  # Try next token
            
            # All tokens failed
            logger.error(f"All PDFEndpoint API tokens failed. Last error: {last_error}")
            return {
                'success': False,
                'error': f"All API tokens failed. Last error: {last_error}"
            }
                
        except Exception as e:
            logger.error(f"PDFEndpoint PDF generation error: {e}")
            return {
                'success': False,
                'error': str(e)
            }

