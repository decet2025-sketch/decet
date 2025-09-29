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
import pyppeteer
from pyppeteer import launch
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
            sanitized_template = self.sanitize_template(template_html)
            
            # Create template
            template = self.jinja_env.from_string(sanitized_template)
            
            # Prepare context data
            context_data = {
                'learner_name': context.learner_name,
                'course_name': context.course_name,
                'completion_date': context.completion_date,
                'organization': context.organization,
                'learner_email': context.learner_email,
                'custom_fields': context.custom_fields or {}
            }
            
            # Add any custom fields to the root context
            if context.custom_fields:
                context_data.update(context.custom_fields)
            
            # Render template
            rendered_html = template.render(**context_data)
            
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

    async def html_to_pdf_pyppeteer(self, html_content: str, filename: str) -> Optional[bytes]:
        """
        Convert HTML to PDF using pyppeteer (headless Chromium).
        """
        try:
            # Launch browser
            browser = await launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )
            
            try:
                # Create new page
                page = await browser.newPage()
                
                # Set viewport
                await page.setViewport({'width': 1200, 'height': 800})
                
                # Set content
                await page.setContent(html_content, waitUntil='networkidle0')
                
                # Emulate screen media
                await page.emulateMedia('screen')
                
                # Generate PDF
                pdf_bytes = await page.pdf({
                    'format': 'A4',
                    'printBackground': True,
                    'margin': {
                        'top': '20mm',
                        'right': '20mm',
                        'bottom': '20mm',
                        'left': '20mm'
                    }
                })
                
                return pdf_bytes
                
            finally:
                await browser.close()
                
        except Exception as e:
            logger.error(f"Error generating PDF with pyppeteer: {e}")
            return None

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
        Convert HTML to PDF with fallback strategy.
        """
        try:
            # Try pyppeteer first
            try:
                pdf_bytes = asyncio.run(self.html_to_pdf_pyppeteer(html_content, filename))
                if pdf_bytes:
                    return PDFGenerationResponse(ok=True, file_id="pdf_generated")
            except Exception as e:
                logger.warning(f"Pyppeteer PDF generation failed: {e}")
            
            # Fallback to external API
            if self.html_to_pdf_api_url:
                try:
                    pdf_bytes = self.html_to_pdf_external_api(html_content, filename)
                    if pdf_bytes:
                        return PDFGenerationResponse(ok=True, file_id="pdf_generated")
                except Exception as e:
                    logger.warning(f"External PDF API failed: {e}")
            
            return PDFGenerationResponse(
                ok=False,
                error="PDF generation failed with all available methods"
            )
            
        except Exception as e:
            logger.error(f"Error in html_to_pdf: {e}")
            return PDFGenerationResponse(
                ok=False,
                error=f"PDF generation error: {str(e)}"
            )

    def generate_certificate_pdf(
        self,
        template_html: str,
        context: CertificateContext,
        filename: str
    ) -> PDFGenerationResponse:
        """
        Generate certificate PDF from template and context.
        """
        try:
            # Render HTML
            rendered_html = self.render_certificate(template_html, context)
            
            # Convert to PDF
            pdf_response = self.html_to_pdf(rendered_html, filename)
            
            return pdf_response
            
        except Exception as e:
            logger.error(f"Error generating certificate PDF: {e}")
            return PDFGenerationResponse(
                ok=False,
                error=f"Certificate generation failed: {str(e)}"
            )

    def preview_certificate(self, template_html: str, context: CertificateContext) -> str:
        """
        Generate preview HTML for certificate template.
        """
        try:
            return self.render_certificate(template_html, context)
        except Exception as e:
            logger.error(f"Error previewing certificate: {e}")
            return f"<p>Error rendering certificate: {str(e)}</p>"
