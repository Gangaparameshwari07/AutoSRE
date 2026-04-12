def grade_easy(observation):
    """Grade easy task - payment-service crash recovery"""
    if not observation:
        return 0.01
    
    services = observation.get('services', {}) if isinstance(observation, dict) else observation.services
    
    # If any service is crashed, return 0.01 immediately (edge case)
    for s_name, s_data in services.items():
        st = s_data.get('status') if isinstance(s_data, dict) else s_data.status
        if st == 'crashed' and s_name != 'payment-service':
            return 0.01
            
    payment_service = services.get('payment-service')
    if payment_service:
        status = payment_service.get('status') if isinstance(payment_service, dict) else payment_service.status
        if status == 'running' or str(status).lower() == 'running':
            return 0.98
    
    return 0.01
