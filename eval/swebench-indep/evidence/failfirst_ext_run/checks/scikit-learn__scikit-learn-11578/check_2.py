import numpy as np
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.model_selection import cross_val_score
from sklearn.datasets import make_classification

def main():
    # Generate a multiclass dataset
    X, y = make_classification(n_samples=200, n_features=5, n_informative=3, 
                               n_redundant=0, n_classes=3, random_state=42)
    
    # We want to verify that LogisticRegressionCV with multi_class='multinomial'
    # uses the multinomial strategy for scoring, not OvR.
    
    # The issue states that internally, _log_reg_scoring_path was creating a 
    # LogisticRegression instance without passing the multi_class parameter,
    # defaulting to 'ovr'. This caused predict_proba to use the OvR normalization
    # instead of softmax when calculating scores like neg_log_loss.
    
    # To check if this is fixed, we can compare the score obtained from 
    # LogisticRegressionCV(multi_class='multinomial') with a manual calculation
    # using the correct multinomial probabilities.
    
    # However, a more direct way to test the fix described in the issue is to 
    # ensure that the internal LogisticRegression object used for scoring respects
    # the multi_class parameter. Since we cannot easily access the internal 
    # _log_reg_scoring_path directly in a stable way across versions without 
    # relying on private APIs which might change, we can rely on the public API 
    # behavior difference.
    
    # If the bug exists:
    # LogisticRegressionCV(multi_class='multinomial').score() or cross_val_score 
    # would calculate log loss using OvR-style probabilities (sigmoid + normalize).
    
    # If the bug is fixed:
    # It should use Softmax probabilities.
    
    # Let's create a scenario where OvR and Multinomial probabilities differ significantly.
    
    lr_cv_multi = LogisticRegressionCV(
        Cs=[1.0], 
        cv=5, 
        scoring='neg_log_loss', 
        multi_class='multinomial', 
        solver='lbfgs',
        random_state=42
    )
    
    lr_cv_ovr = LogisticRegressionCV(
        Cs=[1.0], 
        cv=5, 
        scoring='neg_log_loss', 
        multi_class='ovr', 
        solver='lbfgs',
        random_state=42
    )
    
    # Fit both
    lr_cv_multi.fit(X, y)
    lr_cv_ovr.fit(X, y)
    
    # Get the best score (which is the mean neg_log_loss across folds for the best C)
    # Note: LogisticRegressionCV stores scores_ attribute
    # scores_ shape: (n_cs, n_folds) for binary/OvR, or (n_classes, n_cs, n_folds) for multinomial?
    # Actually for multinomial, it's often averaged. Let's look at the best_score_.
    
    # A robust check: 
    # Train a standard LogisticRegression with multinomial and same C.
    # Calculate its log loss manually using softmax.
    # Compare with LogisticRegressionCV's reported score.
    
    # But simpler: The bug implies that LR_CV(multinomial) behaves like LR_CV(ovr) 
    # regarding scoring metric calculation internally.
    # If fixed, LR_CV(multinomial) should yield a different (usually better/true) 
    # log loss than LR_CV(ovr) because the probability estimates are different.
    
    # However, they might select different Cs. Let's force C=1.0.
    
    # Let's check the internal consistency.
    # If we fit a LogisticRegression(multi_class='multinomial') on the full data,
    # we get coefficients.
    # If we fit LogisticRegressionCV(multi_class='multinomial'), it should find 
    # similar coefficients and report a score consistent with multinomial probs.
    
    # The most direct reproduction from the issue uses `_log_reg_scoring_path`.
    # Although private, it is the specific function mentioned. 
    # In scikit-learn 0.20, this function exists in sklearn.linear_model.logistic.
    
    try:
        from sklearn.linear_model.logistic import _log_reg_scoring_path
    except ImportError:
        # Try alternative location if structure changed slightly, though 0.20 is specific
        from sklearn.linear_model._logistic import _log_reg_scoring_path

    # Reproduce the exact test case from the issue
    np.random.seed(seed=1234)
    samples = 200
    features = 5
    x = np.random.random(size=(samples, features))
    y = np.random.choice(['a', 'b', 'c'], size=samples)
    
    # Use a single fold split as in the issue example to isolate the scoring logic
    test = np.random.choice(range(samples), size=int(samples/10.0), replace=False)
    train = [idx for idx in range(samples) if idx not in test]
    
    # Call the internal function with multi_class='multinomial'
    # Coefs shape: (n_cs, n_classes, n_features+1) or similar
    coefs, _, scores, _ = _log_reg_scoring_path(
        x, y, train, test, 
        fit_intercept=True, 
        scoring='neg_log_loss', 
        multi_class='multinomial',
        Cs=[1.0],
        solver='lbfgs'
    )
    
    # scores is an array of scores for each C. We have only one C.
    # The issue says the score returned was calculated via OvR method.
    # Score index 0 corresponds to C=1.0
    reported_score = scores[0]
    
    # Now calculate what the score SHOULD be if multinomial (softmax) is used correctly.
    # Extract coefficients for the first (and only) C
    # The structure of coefs depends on version. 
    # In 0.20, for multinomial, coefs might be (1, n_classes, n_features) or flattened.
    # Let's instantiate a LR model with these coefficients to check predict_proba.
    
    # _log_reg_scoring_path returns coefs. 
    # Let's fit a standard LR multinomial on the training data with C=1.0 to get comparable coeffs
    # Or better, use the returned coeffs directly if we can interpret them.
    
    # Alternative approach: 
    # Fit a LogisticRegression(multi_class='multinomial') on the training set.
    # Calculate neg_log_loss on test set using its predict_proba.
    # This is the "correct" score.
    # Then compare with the score from _log_reg_scoring_path.
    
    lr_true = LogisticRegression(C=1.0, multi_class='multinomial', solver='lbfgs', fit_intercept=True, random_state=42)
    lr_true.fit(x[train], y[train])
    
    from sklearn.metrics import log_loss
    # log_loss returns positive value, scorer is neg_log_loss so we negate it
    true_neg_log_loss = -log_loss(y[test], lr_true.predict_proba(x[test]), labels=['a','b','c'])
    
    # The reported_score from _log_reg_scoring_path should match true_neg_log_loss
    # if the bug is fixed. If buggy, it will match the OvR calculation.
    
    # Let's also calculate the OvR-based score to ensure they are distinct
    lr_ovr = LogisticRegression(C=1.0, multi_class='ovr', solver='lbfgs', fit_intercept=True, random_state=42)
    lr_ovr.fit(x[train], y[train])
    ovr_neg_log_loss = -log_loss(y[test], lr_ovr.predict_proba(x[test]), labels=['a','b','c'])
    
    # Debug prints (optional, but good for understanding if run manually)
    # print(f"Reported: {reported_score}, True Multi: {true_neg_log_loss}, OVR: {ovr_neg_log_loss}")
    
    # Assert that the reported score is close to the true multinomial score
    # and NOT close to the OvR score (unless they happen to be identical, which is unlikely)
    
    # Tolerance for floating point comparison
    atol = 1e-5
    
    # Check if reported score matches multinomial
    is_multinomial = np.isclose(reported_score, true_neg_log_loss, atol=atol)
    
    # If it's fixed, is_multinomial should be True.
    assert is_multinomial, (
        f"The score from _log_reg_scoring_path ({reported_score}) "
        f"does not match the expected multinomial score ({true_neg_log_loss}). "
        f"It likely still uses OvR scoring ({ovr_neg_log_loss})."
    )

if __name__ == "__main__":
    main()
