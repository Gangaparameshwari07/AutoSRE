def grade_medium(observation):
    """Grade medium task - auth-service memory leak"""
    if observation is None:
        return 0.01
    
    services = observation.get('services', {}) if isinstance(observation, dict) else observation.services
    auth_service = services.get('auth-service')
    
    if auth_service:
        mem_usage = auth_service.get('mem_usage') if isinstance(auth_service, dict) else auth_service.mem_usage
        status = auth_service.get('status') if isinstance(auth_service, dict) else auth_service.status
        
        if status == 'running' and mem_usage < 80:
            return 0.90
    
    return 0.75