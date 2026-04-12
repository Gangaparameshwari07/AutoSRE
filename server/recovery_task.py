def grade_recovery(observation):
    """Grade recovery task - order-service crash recovery"""
    if observation is None:
        return 0.01
    
    services = observation.get('services', {}) if isinstance(observation, dict) else observation.services
    order_service = services.get('order-service')
    
    if order_service:
        status = order_service.get('status') if isinstance(order_service, dict) else order_service.status
        if status == 'running':
            return 0.92
    
    return 0.80