function solution(nums, k) {
    const sorted = nums.slice().sort((a, b) => a - b);
    return sorted.slice(sorted.length - k).reduce((a, b) => a + b, 0);
}
