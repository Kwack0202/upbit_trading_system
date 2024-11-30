# trend_combinations.py

# (장기, 중기, 단기)

trend_combinations = {
    # ---------------------------------------------------------
    # 단기 상승
    ('up', 'up', 'up'): 'up',
    ('up', 'sideway', 'up'): 'up',
    ('up', 'down', 'up'): 'sideway',
    
    ('sideway', 'up', 'up'): 'up',
    ('sideway', 'sideway', 'up'): 'sideway',
    ('sideway', 'down', 'up'): 'sideway',
    
    ('down', 'up', 'up'): 'sideway',
    ('down', 'sideway', 'up'): 'sideway',
    ('down', 'down', 'up'): 'sideway',
    
    # ---------------------------------------------------------
    # 단기 횡보
    ('up', 'up', 'sideway'): 'sideway',
    ('up', 'sideway', 'sideway'): 'sideway',
    ('up', 'down', 'sideway'): 'sideway',
    
    ('sideway', 'up', 'sideway'): 'sideway',
    ('sideway', 'sideway', 'sideway'): 'sideway',
    ('sideway', 'down', 'sideway'): 'sideway',
    
    ('down', 'up', 'sideway'): 'sideway',
    ('down', 'sideway', 'sideway'): 'sideway',
    ('down', 'down', 'sideway'): 'sideway',
    
    # ---------------------------------------------------------
    # 단기 하락
    ('up', 'up', 'down'): 'down',
    ('up', 'sideway', 'down'): 'down',
    ('up', 'down', 'down'): 'down',
    
    ('sideway', 'up', 'down'): 'sideway',
    ('sideway', 'sideway', 'down'): 'down',
    ('sideway', 'down', 'down'): 'down',
    
    ('down', 'up', 'down'): 'down',
    ('down', 'sideway', 'down'): 'down',
    ('down', 'down', 'down'): 'down',
    
}
