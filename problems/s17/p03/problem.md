# p03. BFS 함수 완성 (빈칸 채우기 · 4점)

딕셔너리로 표현한 그래프 `graph` 를 `start_node` 에서 시작해 너비 우선 탐색(BFS)하고, 방문한 순서대로 노드를 담은 리스트를 반환하는 `my_bfs` 함수입니다.
빈칸(`____`) 3곳을 채워 함수를 완성하세요.

- 방문할 노드는 큐에 담고, 넣은 순서대로 하나씩 꺼내 방문합니다.
- 큐에 방문할 노드가 남지 않을 때까지 반복합니다.
- 방문하지 않은 노드를 꺼냈으면 그 노드의 인접 노드를 리스트에 적힌 순서대로 큐에 넣습니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
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
```

## 입출력 예

| 호출 | 반환값 |
|---|---|
| `my_bfs(my_graph, "A")` | `['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']` |
| `my_bfs(g2, 1)` | `[1, 3, 2, 4, 5]` |
