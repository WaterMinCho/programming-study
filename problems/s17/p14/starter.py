def maze_bfs(graph, start):
    n = len(graph)
    m = len(graph[0])
    moves = [(1, 0), (0, 1), (-1, 0), (0, -1)]

    queue = list()
    visited = list()
    queue.append(start)

    while queue:
        node = queue.____

        if node not in visited:
            visited.append(node)
            for move in moves:
                nr = node[0] + move[0]
                nc = node[1] + move[1]
                if nr >= 0 and nr < ____ and nc >= 0 and nc < m:
                    if graph[____][nc] == 0:
                        queue.append((nr, nc))

    return visited


maze = [
    [0, 1, 1, 1, 1, 1],
    [0, 1, 0, 0, 0, 1],
    [0, 1, 0, 1, 0, 1],
    [0, 1, 0, 1, 0, 0],
    [0, 0, 0, 1, 1, 0],
    [1, 1, 1, 1, 1, 0],
]
small = [
    [0, 0, 0, 1],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
]
