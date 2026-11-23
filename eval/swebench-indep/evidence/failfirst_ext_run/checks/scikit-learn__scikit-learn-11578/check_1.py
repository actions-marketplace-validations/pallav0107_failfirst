import numpy as np
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.model_selection import cross_val_score
from sklearn.datasets import make_classification

# Create a multiclass dataset
X, y = make_classification(n_samples=200, n_features=5, n_informative=3, 
                           n_redundant=0, n_classes=3, random_state=42)

# We want to verify that LogisticRegressionCV with multi_class='multinomial'
# uses the correct probability estimates for scoring.
# The bug was that internal LogisticRegression instances used for scoring
# defaulted to 'ovr', causing a mismatch in probabilities (and thus scores)
# compared to what the final model would produce.

# To check this, we can compare the score obtained via cross_val_score using 
# a standalone LogisticRegression(multi_class='multinomial') against the 
# scores stored in LogisticRegressionCV(multi_class='multinomial').
# However, LogisticRegressionCV calculates scores internally during fit.
# A more direct way is to inspect if the internal logic passes multi_class correctly.
# Since we cannot easily inspect private attributes or internal calls without 
# modifying code, we rely on the consistency of the reported best score and 
# the actual performance of the fitted model using the same scorer.

# Let's use neg_log_loss as the scorer, which depends on predict_proba.
scorer = 'neg_log_loss'

# Fit LogisticRegressionCV with multinomial
lr_cv_multi = LogisticRegressionCV(
    Cs=10, 
    cv=5, 
    scoring=scorer, 
    multi_class='multinomial', 
    solver='lbfgs',
    random_state=42
)
lr_cv_multi.fit(X, y)

# Get the best C and the corresponding mean score from CV
best_c = lr_cv_multi.C_[0]
cv_scores = lr_cv_multi.scores_[0] # scores for class 0 (structure varies by version, but usually dict or array)
# In 0.20, scores_ is a dict: {class_label: array of shape (n_cs, n_folds)}
# We need to average across folds for each C to compare with cross_val_score manually.

# Calculate manual cross_val_score for LogisticRegression with the best C and multinomial
lr_manual = LogisticRegression(
    C=best_c, 
    multi_class='multinomial', 
    solver='lbfgs', 
    random_state=42
)

manual_scores = cross_val_score(lr_manual, X, y, cv=5, scoring=scorer)
mean_manual_score = np.mean(manual_scores)

# Get the mean score from LR_CV for the best C
# lr_cv_multi.scores_ is a dict where keys are class labels.
# The values are arrays of shape (n_Cs, n_folds).
# We need to find the index of the best C.
# lr_cv_multi.C_ contains the best C for each class. For multinomial, it's usually a single value or same for all.
# Let's look at the scores structure.
# In 0.20, for multinomial, scores_ might be structured differently than OvR.
# Actually, for multinomial, there is only one set of coefficients, so scores_ might have a specific key or structure.
# Let's assume standard behavior: scores_ is a dict with keys as classes.
# For multinomial, the score is calculated on the whole model, not per-class OvR.
# In scikit-learn 0.20, LogisticRegressionCV with multinomial stores scores in a way that might be aggregated.
# Let's try to access the scores properly.
# According to docs, scores_ is a dict with class labels as keys. For multinomial, the "classes" are still present, 
# but the scoring is done on the full probability distribution.
# The best index is determined by averaging scores across folds and classes? Or just one entry?
# For multinomial, lr_cv_multi.C_ is an array of shape (1,) or (n_classes,)? 
# In 0.20, for multinomial, C_ is shape (1,) if cs is scalar? No, Cs is array.
# Let's check the shape of C_.
# If multi_class='multinomial', C_ has shape (1,) because there's one regularization path for the whole model.
# Wait, in 0.20, C_ shape is (n_classes,) for ovr and (1,) for multinomial? 
# Actually, for multinomial, it's often treated as a single problem.

# Let's get the mean score for the best C from the CV object.
# The best C index is not directly stored, but we can find it.
# lr_cv_multi.scores_ is a dict. For multinomial, does it have multiple keys?
# Yes, it usually has keys for each class, but the scores should be identical or very similar if calculated correctly?
# Actually, for multinomial, the log loss is computed on the full vector.
# In 0.20 implementation, _log_reg_scoring_path returns scores.
# Let's average the scores across all classes and folds for the best C.

# Find the index of best_c in lr_cv_multi.Cs_
cs_array = lr_cv_multi.Cs_
best_c_idx = np.where(cs_array == best_c)[0][0]

# Collect scores for this C index across all folds and classes
all_scores_for_best_c = []
for cls in lr_cv_multi.classes_:
    # scores_[cls] is (n_Cs, n_folds)
    fold_scores = lr_cv_multi.scores_[cls][best_c_idx]
    all_scores_for_best_c.extend(fold_scores)

mean_cv_score = np.mean(all_scores_for_best_c)

# The bug was that internal scoring used OvR probabilities while the final model uses Multinomial.
# This would cause mean_cv_score (calculated with potentially wrong probs during CV) 
# to differ significantly from mean_manual_score (calculated with correct Multinomial probs).
# If fixed, they should be very close.

print(f"Mean CV Score from LR_CV (internal): {mean_cv_score}")
print(f"Mean Manual Score from LR (external): {mean_manual_score}")

# Allow for small numerical differences due to different CV splits or solvers convergence
# But here we use the same data and roughly same process. 
# Note: cross_val_score uses default stratified kfold, LR_CV uses stratified kfold.
# We didn't set cv explicitly in LR_CV to match exactly, but both default to StratifiedKFold(n_splits=5).
# However, random_state might affect splits if not set in CV. LR_CV doesn't take random_state for splits in 0.20?
# Actually, LogisticRegressionCV in 0.20 does not have a random_state parameter for CV splits.
# This introduces variability. To make this robust, we should ensure the CV splits are identical or 
# accept a tolerance.
# Better approach: Use the same CV splitter.

from sklearn.model_selection import StratifiedKFold

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

lr_cv_multi_fixed = LogisticRegressionCV(
    Cs=10, 
    cv=cv, 
    scoring=scorer, 
    multi_class='multinomial', 
    solver='lbfgs'
)
lr_cv_multi_fixed.fit(X, y)

best_c_fixed = lr_cv_multi_fixed.C_[0]
cs_array_fixed = lr_cv_multi_fixed.Cs_
best_c_idx_fixed = np.where(cs_array_fixed == best_c_fixed)[0][0]

all_scores_for_best_c_fixed = []
for cls in lr_cv_multi_fixed.classes_:
    fold_scores = lr_cv_multi_fixed.scores_[cls][best_c_idx_fixed]
    all_scores_for_best_c_fixed.extend(fold_scores)

mean_cv_score_fixed = np.mean(all_scores_for_best_c_fixed)

lr_manual_fixed = LogisticRegression(
    C=best_c_fixed, 
    multi_class='multinomial', 
    solver='lbfgs'
)

manual_scores_fixed = cross_val_score(lr_manual_fixed, X, y, cv=cv, scoring=scorer)
mean_manual_score_fixed = np.mean(manual_scores_fixed)

print(f"Fixed Mean CV Score from LR_CV (internal): {mean_cv_score_fixed}")
print(f"Fixed Mean Manual Score from LR (external): {mean_manual_score_fixed}")

# Assert that the scores are close. If the bug exists, the internal scoring uses OvR probs
# which are different from Multinomial probs, leading to a discrepancy.
# The tolerance is set to account for minor numerical issues but should fail if the method is wrong.
assert np.isclose(mean_cv_score_fixed, mean_manual_score_fixed, atol=1e-3), \
    f"Scores do not match: Internal CV score {mean_cv_score_fixed} vs Manual score {mean_manual_score_fixed}. " \
    "This indicates the internal scoring is not using the correct multi_class probability estimates."

print("Check passed: Internal scoring matches external scoring.")
