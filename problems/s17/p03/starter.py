def my_bfs(graph, start_node):
    queue = list()
    visited = list()

    queue.append(start_node)

    while ____:
        node = queue.pop(____)

        if node not in visited:
            queue.____(graph[node])
            visited.append(node)

    return visited


my_graph = {
    "A": ["B", "C", "D"],
    "B": ["A", "E"],
    "C": ["A", "F", "G"],
    "D": ["A", "H"],
    "E": ["B", "I"],
    "F": ["C", "J"],
    "G": ["C"],
    "H": ["D"],
    "I": ["E"],
    "J": ["F"],
}
g2 = {1: [3, 2], 2: [1, 4], 3: [1, 4, 5], 4: [2, 3], 5: [3]}
