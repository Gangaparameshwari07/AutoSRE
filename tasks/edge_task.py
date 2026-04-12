def grade_edge(observation):
    """Grade edge task - database crash cascade"""
    if observation is None:
        return 0.01
    
    services = observation.get('services', {}) if isinstance(observation, dict) else observation.services
    database = services.get('database')
    gateway = services.get('api-gateway')
    auth = services.get('auth-service')
    
    all_running = True
    for service in [database, gateway, auth]:
        if service:
            status = service.get('status') if isinstance(service, dict) else service.status
            if status != 'running':
                all_running = False
                break
    
    if all_running:
        return 0.88
    
    return 0.75