def maze_dfs(graph, start, goal):
    n = len(graph)
    m = len(graph[0])
    moves = [(1, 0), (0, 1), (-1, 0), (0, -1)]

    stack = list()
    visited = list()
    stack.append(start)

    while stack:
        node = stack.pop()

        if node not in visited:
            visited.append(node)
            if node == goal:
                break
            for move in reversed(moves):
                nr = node[0] + move[0]
                nc = node[1] + move[1]
                if nr >= 0 and nr < n and nc >= 0 and nc < ____:
                    if graph[nr][nc] == ____:
                        stack.append(____)

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
