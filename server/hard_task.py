def grade_hard(observation):
    """Grade hard task - database cascading failure"""
    if observation is None:
        return 0.01
    
    services = observation.get('services', {}) if isinstance(observation, dict) else observation.services
    database = services.get('database')
    gateway = services.get('api-gateway')
    
    db_healthy = False
    gateway_healthy = False
    
    if database:
        status = database.get('status') if isinstance(database, dict) else database.status
        latency = database.get('latency_ms') if isinstance(database, dict) else database.latency_ms
        if status == 'running' and latency < 100:
            db_healthy = True
    
    if gateway:
        status = gateway.get('status') if isinstance(gateway, dict) else gateway.status
        if status == 'running':
            gateway_healthy = True
    
    if db_healthy and gateway_healthy:
        return 0.86
    
    return 0.70