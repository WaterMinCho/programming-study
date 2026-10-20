function solution(nums, k) {
    let total = 0;
    for (let i = 0; i < k; i++) {
        total += nums[i];
    }
    return total;
}
