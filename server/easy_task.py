def grade_easy(observation):
    """Grade easy task - payment-service crash recovery"""
    if observation is None:
        return 0.01
    
    # Check if payment-service is running
    services = observation.get('services', {}) if isinstance(observation, dict) else observation.services
    payment_service = services.get('payment-service')
    
    if payment_service:
        status = payment_service.get('status') if isinstance(payment_service, dict) else payment_service.status
        if status == 'running' or str(status).lower() == 'running':
            return 0.98
    
    return 0.85