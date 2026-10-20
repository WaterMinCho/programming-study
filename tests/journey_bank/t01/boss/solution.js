function solution(nums, k) {
    const sorted = [...nums].sort((a, b) => b - a);
    let total = 0;
    for (let i = 0; i < k; i++) {
        total += sorted[i];
    }
    return total;
}
