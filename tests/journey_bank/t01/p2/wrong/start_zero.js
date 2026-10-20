function solution(nums) {
    let best = 0;
    for (const x of nums) {
        best = Math.max(best, x);
    }
    return best;
}
