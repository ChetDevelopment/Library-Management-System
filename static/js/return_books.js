
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('return-form');
    const submitBtn = document.getElementById('submit-btn');

    // Form submission
    form.addEventListener('submit', function (e) {
        e.preventDefault();

        // Show loading state
        submitBtn.disabled = true;
        submitBtn.classList.add('loading');
        submitBtn.innerHTML = 'Processing Return...';

        // Simulate API call
        setTimeout(() => {
            // Create success message
            const successMessage = document.createElement('div');
            successMessage.className = 'alert alert-success';
            successMessage.innerHTML = `
                        <i class="ri-checkbox-circle-line"></i>
                        <div>
                            <h4>Book Returned Successfully!</h4>
                            <p>Your book has been returned to the library. Thank you for returning it on time!</p>
                        </div>
                    `;

            // Style the success message
            successMessage.style.cssText = `
                        background: rgba(76, 201, 240, 0.1);
                        color: #0c5460;
                        border: 1px solid rgba(76, 201, 240, 0.2);
                        padding: 16px;
                        border-radius: 12px;
                        margin-bottom: 20px;
                        display: flex;
                        align-items: flex-start;
                        gap: 10px;
                        animation: fadeInUp 0.5s ease;
                    `;

            // Insert before the form
            form.parentNode.insertBefore(successMessage, form);

            // Update the book info to show returned status
            const bookTitle = document.querySelector('.book-title');
            if (bookTitle) {
                const returnedBadge = document.createElement('span');
                returnedBadge.textContent = 'Returned';
                returnedBadge.style.cssText = `
                            background: var(--success);
                            color: white;
                            padding: 4px 10px;
                            border-radius: 20px;
                            font-size: 12px;
                            font-weight: 600;
                            margin-left: 10px;
                        `;
                bookTitle.appendChild(returnedBadge);
            }

            // Update the status indicator
            const statusIndicator = document.querySelector('.status-indicator');
            if (statusIndicator) {
                statusIndicator.innerHTML = `
                            <i class="ri-checkbox-circle-line" style="color: var(--success);"></i>
                            <div class="status-text">
                                <strong>Status:</strong> This book has been successfully returned.
                            </div>
                        `;
                statusIndicator.style.background = 'rgba(76, 201, 240, 0.05)';
                statusIndicator.style.border = '1px solid rgba(76, 201, 240, 0.1)';
            }

            // Update the button to show completed state
            submitBtn.disabled = true;
            submitBtn.classList.remove('loading');
            submitBtn.innerHTML = '<i class="ri-check-line"></i> Successfully Returned';
            submitBtn.style.background = 'var(--success)';

            // Add a button to go back to dashboard
            const backButton = document.createElement('a');
            backButton.href = "{{ url_for('dashboard') }}";
            backButton.className = 'btn btn-primary';
            backButton.innerHTML = '<i class="ri-home-4-line"></i> Back to Dashboard';
            backButton.style.marginTop = '15px';
            backButton.style.width = '100%';

            form.appendChild(backButton);

            // Show fine notification if applicable
            {% if is_overdue %}
            setTimeout(() => {
                const fineAlert = document.createElement('div');
                fineAlert.className = 'alert alert-warning';
                fineAlert.innerHTML = `
                            <i class="ri-money-dollar-circle-line"></i>
                            <div>
                                <h4>Overdue Fine Applied</h4>
                                <p>This book was returned after the due date. A fine has been applied to your account.</p>
                                <a href="{{ url_for('pay_fine') }}" class="btn btn-warning btn-sm" style="margin-top: 10px;">
                                    <i class="ri-bank-card-line"></i> Pay Fine Now
                                </a>
                            </div>
                        `;
                fineAlert.style.cssText = `
                            background: rgba(243, 156, 18, 0.1);
                            color: #856404;
                            border: 1px solid rgba(243, 156, 18, 0.2);
                            padding: 16px;
                            border-radius: 12px;
                            margin-bottom: 20px;
                            display: flex;
                            align-items: flex-start;
                            gap: 10px;
                            animation: fadeInUp 0.5s ease;
                        `;

                form.parentNode.insertBefore(fineAlert, form);
            }, 500);
            {% endif %}
        }, 2000);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function (e) {
        // Enter to submit form
        if (e.key === 'Enter' && !submitBtn.disabled) {
            form.dispatchEvent(new Event('submit'));
        }

        // Escape to cancel
        if (e.key === 'Escape') {
            window.location.href = "{{ url_for('dashboard') }}";
        }
    });

    // Add styles for success message
    const style = document.createElement('style');
    style.textContent = `
                .alert-success {
                    background: rgba(76, 201, 240, 0.1);
                    color: #0c5460;
                    border: 1px solid rgba(76, 201, 240, 0.2);
                }
                .alert-success h4 {
                    margin: 0 0 5px 0;
                    font-size: 16px;
                }
                .alert-success p {
                    margin: 0;
                    font-size: 14px;
                }
                .btn-sm {
                    padding: 8px 16px;
                    font-size: 14px;
                }
            `;
    document.head.appendChild(style);
});
