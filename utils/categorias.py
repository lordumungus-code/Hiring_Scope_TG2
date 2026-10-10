"""Categorias de serviço do site (as mesmas do formulário de cadastro de serviço)."""

CATEGORIAS_POR_GRUPO = [
    ('Casa & Serviços', ['Construção', 'Limpeza', 'Jardinagem', 'Assistência Técnica']),
    ('Profissional & Negócios', ['Tecnologia', 'Design', 'Marketing', 'Contabilidade']),
    ('Pessoas & Cuidados', ['Saúde', 'Beleza & Estética', 'Bem-estar & Fitness', 'Educação']),
    ('Outros Serviços', ['Fotografia', 'Eventos', 'Música', 'Pets', 'Automotivo', 'Transporte & Mudança', 'Segurança']),
]

CATEGORIAS = [categoria for _, categorias in CATEGORIAS_POR_GRUPO for categoria in categorias]
