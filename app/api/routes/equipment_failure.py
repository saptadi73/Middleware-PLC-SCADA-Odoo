"""
Form routes untuk Equipment Failure Report
Handles GET /scada/failure-report/input dan POST /scada/failure-report/submit
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.equipment_failure_service import get_equipment_failure_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scada/failure-report/input", response_class=HTMLResponse)
async def failure_report_input_form() -> str:
    """
    Display equipment failure report input form.
    GET /scada/failure-report/input
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Equipment Failure Report</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 8px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                padding: 40px;
                width: 100%;
                max-width: 500px;
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                font-size: 28px;
                color: #333;
                margin-bottom: 5px;
            }
            
            .header p {
                color: #666;
                font-size: 14px;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            label {
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 500;
                font-size: 14px;
            }
            
            input[type="text"],
            input[type="datetime-local"],
            textarea {
                width: 100%;
                padding: 10px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-family: inherit;
                font-size: 14px;
                transition: border-color 0.3s;
            }
            
            input[type="text"]:focus,
            input[type="datetime-local"]:focus,
            textarea:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            
            textarea {
                resize: vertical;
                min-height: 100px;
            }
            
            .required {
                color: #e74c3c;
            }
            
            .form-actions {
                display: flex;
                gap: 10px;
                margin-top: 30px;
            }
            
            button {
                flex: 1;
                padding: 12px 20px;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.3s;
            }
            
            .btn-submit {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            
            .btn-submit:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }
            
            .btn-submit:active {
                transform: translateY(0);
            }
            
            .btn-reset {
                background: #f0f0f0;
                color: #333;
                border: 1px solid #ddd;
            }
            
            .btn-reset:hover {
                background: #e8e8e8;
            }
            
            .loading {
                display: none;
                text-align: center;
                color: #666;
                font-size: 14px;
                margin-top: 15px;
            }
            
            .loading.show {
                display: block;
            }
            
            .spinner {
                display: inline-block;
                width: 16px;
                height: 16px;
                border: 2px solid #f3f3f3;
                border-top: 2px solid #667eea;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
                margin-right: 8px;
                vertical-align: middle;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .alert {
                padding: 12px 16px;
                border-radius: 4px;
                margin-bottom: 20px;
                display: none;
            }
            
            .alert.show {
                display: block;
            }
            
            .alert-success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            
            .alert-error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            
            .help-text {
                font-size: 12px;
                color: #999;
                margin-top: 4px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ Equipment Failure Report</h1>
                <p>Report equipment failure atau kerusakan peralatan</p>
            </div>
            
            <div id="alert" class="alert"></div>
            
            <form id="failureReportForm">
                <div class="form-group">
                    <label for="equipmentCode">
                        Equipment Code <span class="required">*</span>
                    </label>
                    <input 
                        type="text" 
                        id="equipmentCode" 
                        name="equipment_code" 
                        placeholder="e.g., PLC01, SILO_A" 
                        required
                    >
                    <div class="help-text">Kode peralatan dari sistem SCADA</div>
                </div>
                
                <div class="form-group">
                    <label for="description">
                        Deskripsi Failure <span class="required">*</span>
                    </label>
                    <textarea 
                        id="description" 
                        name="description" 
                        placeholder="Jelaskan jenis kerusakan atau masalah yang terjadi..." 
                        required
                    ></textarea>
                    <div class="help-text">Detail lengkap tentang failure atau kerusakan</div>
                </div>
                
                <div class="form-group">
                    <label for="date">
                        Waktu Failure (Opsional)
                    </label>
                    <input 
                        type="datetime-local" 
                        id="date" 
                        name="date"
                    >
                    <div class="help-text">Jika kosong, akan menggunakan waktu server saat ini</div>
                </div>
                
                <div class="form-actions">
                    <button type="button" class="btn-reset" onclick="resetForm()">Reset</button>
                    <button type="submit" class="btn-submit">Submit Report</button>
                </div>
                
                <div class="loading" id="loading">
                    <span class="spinner"></span>Processing...
                </div>
            </form>
        </div>
        
        <script>
            const form = document.getElementById('failureReportForm');
            const alertDiv = document.getElementById('alert');
            const loadingDiv = document.getElementById('loading');
            
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                // Validate required fields
                const equipmentCode = document.getElementById('equipmentCode').value.trim();
                const description = document.getElementById('description').value.trim();
                
                if (!equipmentCode) {
                    showAlert('Equipment Code required', 'error');
                    return;
                }
                
                if (!description) {
                    showAlert('Description required', 'error');
                    return;
                }
                
                try {
                    loadingDiv.classList.add('show');
                    hideAlert();
                    
                    // Get date value and convert if needed
                    let date = document.getElementById('date').value;
                    if (date) {
                        // Convert datetime-local to YYYY-MM-DD HH:MM:SS format
                        date = date.replace('T', ' ') + ':00';
                    }
                    
                    const payload = {
                        equipment_code: equipmentCode,
                        description: description
                    };
                    
                    if (date) {
                        payload.date = date;
                    }
                    
                    const response = await fetch('/scada/failure-report/submit', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(payload)
                    });
                    
                    const result = await response.json();
                    
                    if (result.status === 'success') {
                        showAlert('✓ Failure report submitted successfully!', 'success');
                        form.reset();
                        
                        // Auto redirect after 2 seconds
                        setTimeout(() => {
                            form.reset();
                        }, 2000);
                    } else {
                        showAlert('✗ ' + (result.message || 'Failed to submit report'), 'error');
                    }
                } catch (error) {
                    showAlert('✗ Error: ' + error.message, 'error');
                    console.error('Error:', error);
                } finally {
                    loadingDiv.classList.remove('show');
                }
            });
            
            function resetForm() {
                form.reset();
                hideAlert();
            }
            
            function showAlert(message, type) {
                alertDiv.className = 'alert show alert-' + type;
                alertDiv.textContent = message;
            }
            
            function hideAlert() {
                alertDiv.classList.remove('show');
            }
            
            // Set current datetime as default
            document.getElementById('date').addEventListener('focus', function() {
                if (!this.value) {
                    const now = new Date();
                    const offset = now.getTimezoneOffset() * 60000;
                    const localISOTime = new Date(now - offset).toISOString().slice(0, 16);
                    this.value = localISOTime;
                }
            });
        </script>
    </body>
    </html>
    """
    return html_content


@router.post("/scada/failure-report/submit")
async def failure_report_submit(
    equipment_code: str = Form(...),
    description: str = Form(...),
    date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> Any:
    """
    Handle POST /scada/failure-report/submit dari form.
    
    Form data:
    - equipment_code: Equipment code
    - description: Failure description
    - date (optional): Timestamp
    """
    try:
        if not equipment_code or not description:
            return {
                "status": "error",
                "message": "Equipment code dan description diperlukan"
            }
        
        service = get_equipment_failure_service(db=db)
        
        result = await service.create_failure_report(
            equipment_code=equipment_code,
            description=description,
            date=date,
        )
        
        return result
    
    except Exception as exc:
        logger.exception(
            "Error submitting failure report: %s",
            str(exc),
        )
        return {
            "status": "error",
            "message": f"Failed to submit failure report: {str(exc)}"
        }
