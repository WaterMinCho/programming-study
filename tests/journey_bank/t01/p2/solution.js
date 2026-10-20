function solution(nums) {
    let best = nums[0];
    for (const x of nums) {
        if (x > best) {
            best = x;
        }
    }
    return best;
}
