function solution(nums) {
    return nums.reduce((a, b) => (a > b ? a : b));
}
