"""
Statistical Engine - Analyzes A/B test results for statistical significance
"""
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from scipy import stats
from statsmodels.stats.power import tt_ind_solve_power
from statsmodels.stats.proportion import proportions_ztest
import pandas as pd

from core.logging import get_logger
from ..domain.models import Experiment, ExperimentVariant, StatisticalTest

logger = get_logger(__name__)


class StatisticalEngine:
    """Performs statistical analysis on A/B test results"""
    
    def __init__(self):
        self.test_methods = {
            StatisticalTest.T_TEST.value: self._perform_t_test,
            StatisticalTest.CHI_SQUARED.value: self._perform_chi_squared,
            StatisticalTest.MANN_WHITNEY_U.value: self._perform_mann_whitney,
            StatisticalTest.ANOVA.value: self._perform_anova,
            StatisticalTest.BAYESIAN.value: self._perform_bayesian_analysis
        }
        
    async def analyze(
        self,
        experiment: Experiment,
        metrics: Dict[str, Any],
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """Main analysis entry point"""
        logger.info(f"Starting analysis for experiment {experiment.id}")
        
        # Get test method
        test_method = self.test_methods.get(
            experiment.statistical_test,
            self._perform_t_test
        )
        
        # Prepare data
        variant_data = self._prepare_variant_data(metrics)
        
        # Run statistical test
        test_results = test_method(
            variant_data,
            confidence_level
        )
        
        # Calculate effect sizes
        effect_sizes = self._calculate_effect_sizes(variant_data)
        
        # Check sample size adequacy
        sample_size_analysis = self._analyze_sample_size(
            variant_data,
            experiment.minimum_detectable_effect,
            confidence_level
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            test_results,
            effect_sizes,
            sample_size_analysis,
            experiment
        )
        
        # Compile results
        results = {
            "variants": self._format_variant_results(
                variant_data,
                test_results,
                effect_sizes
            ),
            "statistical_significance": test_results,
            "effect_sizes": effect_sizes,
            "sample_size_analysis": sample_size_analysis,
            "recommendations": recommendations,
            "confidence_level": confidence_level,
            "test_method": experiment.statistical_test
        }
        
        # Add segment analysis if available
        if "segments" in metrics:
            results["segments"] = self._analyze_segments(
                metrics["segments"],
                confidence_level
            )
            
        logger.info(f"Completed analysis for experiment {experiment.id}")
        
        return results
        
    def _prepare_variant_data(
        self,
        metrics: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Prepare variant data for analysis"""
        variant_data = {}
        
        for variant_id, variant_metrics in metrics.get("variants", {}).items():
            variant_data[variant_id] = {
                "participants": variant_metrics.get("participant_count", 0),
                "conversions": variant_metrics.get("conversions", 0),
                "conversion_rate": variant_metrics.get("conversion_rate", 0),
                "revenue": variant_metrics.get("revenue", 0),
                "revenue_per_user": variant_metrics.get("revenue_per_user", 0),
                "event_count": variant_metrics.get("event_count", 0)
            }
            
        return variant_data
        
    def _perform_t_test(
        self,
        variant_data: Dict[str, Dict[str, Any]],
        confidence_level: float
    ) -> Dict[str, Any]:
        """Perform t-test for continuous metrics"""
        results = {
            "test_type": "t_test",
            "significant": False,
            "p_values": {},
            "confidence_intervals": {}
        }
        
        # Get control and treatment variants
        control_data = None
        treatment_data = []
        
        for variant_id, data in variant_data.items():
            if control_data is None:  # First variant is control
                control_data = data
                control_id = variant_id
            else:
                treatment_data.append((variant_id, data))
                
        if not control_data or not treatment_data:
            return results
            
        # Compare each treatment to control
        for treatment_id, treatment in treatment_data:
            # For conversion rate comparison
            control_conversions = control_data["conversions"]
            control_participants = control_data["participants"]
            treatment_conversions = treatment["conversions"]
            treatment_participants = treatment["participants"]
            
            if control_participants == 0 or treatment_participants == 0:
                continue
                
            # Proportion test for conversion rates
            successes = [control_conversions, treatment_conversions]
            nobs = [control_participants, treatment_participants]
            
            try:
                z_stat, p_value = proportions_ztest(successes, nobs)
                
                # Calculate confidence interval
                control_rate = control_conversions / control_participants
                treatment_rate = treatment_conversions / treatment_participants
                rate_diff = treatment_rate - control_rate
                
                # Standard error for difference in proportions
                se = np.sqrt(
                    (control_rate * (1 - control_rate) / control_participants) +
                    (treatment_rate * (1 - treatment_rate) / treatment_participants)
                )
                
                z_critical = stats.norm.ppf((1 + confidence_level) / 2)
                ci_lower = rate_diff - z_critical * se
                ci_upper = rate_diff + z_critical * se
                
                results["p_values"][f"{control_id}_vs_{treatment_id}"] = p_value
                results["confidence_intervals"][f"{control_id}_vs_{treatment_id}"] = {
                    "lower": ci_lower,
                    "upper": ci_upper,
                    "difference": rate_diff
                }
                
                if p_value < (1 - confidence_level):
                    results["significant"] = True
                    
            except Exception as e:
                logger.error(f"Error in t-test calculation: {e}")
                
        return results
        
    def _perform_chi_squared(
        self,
        variant_data: Dict[str, Dict[str, Any]],
        confidence_level: float
    ) -> Dict[str, Any]:
        """Perform chi-squared test for categorical outcomes"""
        results = {
            "test_type": "chi_squared",
            "significant": False,
            "chi2_statistic": None,
            "p_value": None,
            "degrees_of_freedom": None
        }
        
        # Create contingency table
        variants = list(variant_data.keys())
        if len(variants) < 2:
            return results
            
        # Build 2xN contingency table (conversions vs non-conversions)
        conversions = []
        non_conversions = []
        
        for variant_id in variants:
            data = variant_data[variant_id]
            conv = data["conversions"]
            participants = data["participants"]
            
            conversions.append(conv)
            non_conversions.append(participants - conv)
            
        contingency_table = np.array([conversions, non_conversions])
        
        try:
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
            
            results["chi2_statistic"] = chi2
            results["p_value"] = p_value
            results["degrees_of_freedom"] = dof
            results["significant"] = p_value < (1 - confidence_level)
            
        except Exception as e:
            logger.error(f"Error in chi-squared test: {e}")
            
        return results
        
    def _perform_mann_whitney(
        self,
        variant_data: Dict[str, Dict[str, Any]],
        confidence_level: float
    ) -> Dict[str, Any]:
        """Perform Mann-Whitney U test for non-parametric data"""
        results = {
            "test_type": "mann_whitney_u",
            "significant": False,
            "u_statistic": None,
            "p_value": None
        }
        
        # This would require raw data points, not just aggregates
        # For now, we'll use the aggregate data as a proxy
        
        variants = list(variant_data.keys())
        if len(variants) < 2:
            return results
            
        # Compare first two variants
        control_data = variant_data[variants[0]]
        treatment_data = variant_data[variants[1]]
        
        # Create synthetic data based on rates
        control_values = self._generate_synthetic_data(
            control_data["conversions"],
            control_data["participants"]
        )
        
        treatment_values = self._generate_synthetic_data(
            treatment_data["conversions"],
            treatment_data["participants"]
        )
        
        try:
            u_stat, p_value = stats.mannwhitneyu(
                control_values,
                treatment_values,
                alternative='two-sided'
            )
            
            results["u_statistic"] = u_stat
            results["p_value"] = p_value
            results["significant"] = p_value < (1 - confidence_level)
            
        except Exception as e:
            logger.error(f"Error in Mann-Whitney U test: {e}")
            
        return results
        
    def _perform_anova(
        self,
        variant_data: Dict[str, Dict[str, Any]],
        confidence_level: float
    ) -> Dict[str, Any]:
        """Perform ANOVA for multiple variants"""
        results = {
            "test_type": "anova",
            "significant": False,
            "f_statistic": None,
            "p_value": None
        }
        
        if len(variant_data) < 3:
            # ANOVA requires at least 3 groups
            return self._perform_t_test(variant_data, confidence_level)
            
        # Generate synthetic data for each variant
        variant_samples = []
        
        for variant_id, data in variant_data.items():
            samples = self._generate_synthetic_data(
                data["conversions"],
                data["participants"]
            )
            variant_samples.append(samples)
            
        try:
            f_stat, p_value = stats.f_oneway(*variant_samples)
            
            results["f_statistic"] = f_stat
            results["p_value"] = p_value
            results["significant"] = p_value < (1 - confidence_level)
            
            # If significant, perform post-hoc tests
            if results["significant"]:
                results["post_hoc"] = self._perform_post_hoc_tests(
                    variant_samples,
                    list(variant_data.keys()),
                    confidence_level
                )
                
        except Exception as e:
            logger.error(f"Error in ANOVA: {e}")
            
        return results
        
    def _perform_bayesian_analysis(
        self,
        variant_data: Dict[str, Dict[str, Any]],
        confidence_level: float
    ) -> Dict[str, Any]:
        """Perform Bayesian analysis"""
        results = {
            "test_type": "bayesian",
            "significant": False,
            "probabilities": {},
            "expected_loss": {}
        }
        
        # Use Beta distributions for conversion rates
        beta_params = {}
        
        for variant_id, data in variant_data.items():
            # Beta distribution parameters
            alpha = data["conversions"] + 1  # Prior of 1
            beta = data["participants"] - data["conversions"] + 1
            
            beta_params[variant_id] = {
                "alpha": alpha,
                "beta": beta,
                "mean": alpha / (alpha + beta),
                "variance": (alpha * beta) / ((alpha + beta)**2 * (alpha + beta + 1))
            }
            
        # Calculate probability of each variant being best
        num_samples = 10000
        samples = {}
        
        for variant_id, params in beta_params.items():
            samples[variant_id] = np.random.beta(
                params["alpha"],
                params["beta"],
                num_samples
            )
            
        # Calculate win probabilities
        for variant_id in beta_params:
            variant_samples = samples[variant_id]
            wins = 0
            
            for i in range(num_samples):
                is_best = True
                for other_id in beta_params:
                    if other_id != variant_id:
                        if samples[other_id][i] > variant_samples[i]:
                            is_best = False
                            break
                            
                if is_best:
                    wins += 1
                    
            results["probabilities"][variant_id] = wins / num_samples
            
        # Calculate expected loss
        for variant_id in beta_params:
            # Expected loss = probability of not choosing this variant * 
            # expected difference if this variant is actually better
            expected_loss = 0
            variant_mean = beta_params[variant_id]["mean"]
            
            for other_id in beta_params:
                if other_id != variant_id:
                    other_mean = beta_params[other_id]["mean"]
                    if variant_mean > other_mean:
                        prob_choose_other = results["probabilities"][other_id]
                        expected_loss += prob_choose_other * (variant_mean - other_mean)
                        
            results["expected_loss"][variant_id] = expected_loss
            
        # Determine significance based on probability threshold
        max_prob = max(results["probabilities"].values())
        results["significant"] = max_prob > confidence_level
        
        return results
        
    def _calculate_effect_sizes(
        self,
        variant_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate effect sizes between variants"""
        effect_sizes = {
            "cohens_d": {},
            "relative_uplift": {},
            "absolute_uplift": {}
        }
        
        # Get control variant (first one)
        variants = list(variant_data.keys())
        if len(variants) < 2:
            return effect_sizes
            
        control_id = variants[0]
        control_data = variant_data[control_id]
        control_rate = control_data["conversion_rate"]
        
        # Calculate effect sizes for each treatment
        for variant_id, data in variant_data.items():
            if variant_id == control_id:
                continue
                
            treatment_rate = data["conversion_rate"]
            
            # Absolute uplift
            absolute_uplift = treatment_rate - control_rate
            effect_sizes["absolute_uplift"][variant_id] = absolute_uplift
            
            # Relative uplift
            if control_rate > 0:
                relative_uplift = (treatment_rate - control_rate) / control_rate
                effect_sizes["relative_uplift"][variant_id] = relative_uplift
            else:
                effect_sizes["relative_uplift"][variant_id] = None
                
            # Cohen's d for proportions
            pooled_rate = (
                (control_data["conversions"] + data["conversions"]) /
                (control_data["participants"] + data["participants"])
            )
            
            if pooled_rate > 0 and pooled_rate < 1:
                pooled_se = np.sqrt(pooled_rate * (1 - pooled_rate))
                cohens_d = absolute_uplift / pooled_se
                effect_sizes["cohens_d"][variant_id] = cohens_d
            else:
                effect_sizes["cohens_d"][variant_id] = None
                
        return effect_sizes
        
    def _analyze_sample_size(
        self,
        variant_data: Dict[str, Dict[str, Any]],
        minimum_detectable_effect: float,
        confidence_level: float
    ) -> Dict[str, Any]:
        """Analyze sample size adequacy"""
        analysis = {
            "current_sample_sizes": {},
            "required_sample_sizes": {},
            "power_analysis": {},
            "is_adequate": True
        }
        
        # Get baseline conversion rate
        variants = list(variant_data.keys())
        if not variants:
            return analysis
            
        baseline_rate = variant_data[variants[0]]["conversion_rate"]
        
        for variant_id, data in variant_data.items():
            current_size = data["participants"]
            analysis["current_sample_sizes"][variant_id] = current_size
            
            # Calculate required sample size
            if baseline_rate > 0 and baseline_rate < 1:
                # Effect size for proportions
                effect_size = minimum_detectable_effect * baseline_rate / np.sqrt(
                    baseline_rate * (1 - baseline_rate)
                )
                
                try:
                    required_size = tt_ind_solve_power(
                        effect_size=effect_size,
                        alpha=1 - confidence_level,
                        power=0.8,
                        ratio=1
                    )
                    
                    analysis["required_sample_sizes"][variant_id] = int(required_size)
                    
                    # Calculate current power
                    if current_size > 0:
                        current_power = tt_ind_solve_power(
                            effect_size=effect_size,
                            nobs1=current_size,
                            alpha=1 - confidence_level,
                            ratio=1
                        )
                        analysis["power_analysis"][variant_id] = current_power
                        
                        if current_size < required_size:
                            analysis["is_adequate"] = False
                            
                except Exception as e:
                    logger.error(f"Error in power analysis: {e}")
                    
        return analysis
        
    def _generate_recommendations(
        self,
        test_results: Dict[str, Any],
        effect_sizes: Dict[str, Any],
        sample_size_analysis: Dict[str, Any],
        experiment: Experiment
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Check statistical significance
        if test_results.get("significant"):
            # Find winning variant
            max_uplift = 0
            winning_variant = None
            
            for variant_id, uplift in effect_sizes.get("relative_uplift", {}).items():
                if uplift and uplift > max_uplift:
                    max_uplift = uplift
                    winning_variant = variant_id
                    
            if winning_variant:
                recommendations.append({
                    "type": "winner_found",
                    "priority": "high",
                    "message": f"Variant {winning_variant} shows statistically significant improvement "
                              f"with {max_uplift*100:.1f}% relative uplift",
                    "action": "Consider implementing this variant as the new default"
                })
        else:
            # No significant difference
            if sample_size_analysis.get("is_adequate"):
                recommendations.append({
                    "type": "no_difference",
                    "priority": "medium",
                    "message": "No statistically significant difference found between variants",
                    "action": "Consider stopping the experiment or testing more dramatic variations"
                })
            else:
                # Need more data
                avg_current = np.mean(list(
                    sample_size_analysis.get("current_sample_sizes", {}).values()
                ))
                avg_required = np.mean(list(
                    sample_size_analysis.get("required_sample_sizes", {}).values()
                ))
                
                if avg_current > 0 and avg_required > 0:
                    progress = (avg_current / avg_required) * 100
                    recommendations.append({
                        "type": "insufficient_data",
                        "priority": "high",
                        "message": f"Experiment has reached {progress:.0f}% of required sample size",
                        "action": "Continue running the experiment to gather more data"
                    })
                    
        # Check for practical significance
        max_absolute_uplift = max(
            effect_sizes.get("absolute_uplift", {}).values(),
            default=0
        )
        
        if max_absolute_uplift > 0 and max_absolute_uplift < 0.01:
            recommendations.append({
                "type": "small_effect",
                "priority": "low",
                "message": "Effect size is very small and may not be practically significant",
                "action": "Consider whether the improvement justifies implementation costs"
            })
            
        # Check experiment duration
        if experiment.start_date:
            duration = (datetime.utcnow() - experiment.start_date).days
            
            if duration > 30:
                recommendations.append({
                    "type": "long_running",
                    "priority": "medium",
                    "message": f"Experiment has been running for {duration} days",
                    "action": "Consider concluding the experiment if no new insights are expected"
                })
                
        return recommendations
        
    def _format_variant_results(
        self,
        variant_data: Dict[str, Dict[str, Any]],
        test_results: Dict[str, Any],
        effect_sizes: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Format variant results for output"""
        formatted_results = []
        
        variants = list(variant_data.keys())
        control_id = variants[0] if variants else None
        
        for variant_id, data in variant_data.items():
            result = {
                "id": variant_id,
                "is_control": variant_id == control_id,
                "participants": data["participants"],
                "conversions": data["conversions"],
                "conversion_rate": data["conversion_rate"],
                "revenue": data.get("revenue", 0),
                "revenue_per_user": data.get("revenue_per_user", 0)
            }
            
            # Add statistical results
            if variant_id != control_id:
                # P-value
                p_value_key = f"{control_id}_vs_{variant_id}"
                result["p_value"] = test_results.get("p_values", {}).get(p_value_key)
                
                # Confidence interval
                ci_data = test_results.get("confidence_intervals", {}).get(p_value_key, {})
                result["confidence_interval"] = {
                    "lower": ci_data.get("lower"),
                    "upper": ci_data.get("upper")
                }
                
                # Effect sizes
                result["absolute_uplift"] = effect_sizes.get("absolute_uplift", {}).get(variant_id)
                result["relative_uplift"] = effect_sizes.get("relative_uplift", {}).get(variant_id)
                result["cohens_d"] = effect_sizes.get("cohens_d", {}).get(variant_id)
                
                # Significance
                result["is_statistically_significant"] = (
                    result.get("p_value") and 
                    result["p_value"] < (1 - test_results.get("confidence_level", 0.95))
                )
                
            # Bayesian results
            if "probabilities" in test_results:
                result["probability_best"] = test_results["probabilities"].get(variant_id)
                result["expected_loss"] = test_results["expected_loss"].get(variant_id)
                
            formatted_results.append(result)
            
        return formatted_results
        
    def _analyze_segments(
        self,
        segment_data: Dict[str, Any],
        confidence_level: float
    ) -> Dict[str, Any]:
        """Analyze results by segments"""
        segment_results = {}
        
        for segment_field, segments in segment_data.items():
            segment_analysis = {}
            
            for segment_value, metrics in segments.items():
                # Prepare variant data for this segment
                variant_data = self._prepare_variant_data({"variants": metrics})
                
                # Run simplified analysis
                if len(variant_data) >= 2:
                    test_results = self._perform_t_test(variant_data, confidence_level)
                    effect_sizes = self._calculate_effect_sizes(variant_data)
                    
                    segment_analysis[segment_value] = {
                        "metrics": metrics,
                        "significant": test_results.get("significant", False),
                        "effect_sizes": effect_sizes
                    }
                    
            segment_results[segment_field] = segment_analysis
            
        return segment_results
        
    def _generate_synthetic_data(
        self,
        successes: int,
        trials: int
    ) -> np.ndarray:
        """Generate synthetic binary data for statistical tests"""
        if trials == 0:
            return np.array([])
            
        # Create array with appropriate number of 1s and 0s
        data = np.concatenate([
            np.ones(successes),
            np.zeros(trials - successes)
        ])
        
        return data
        
    def _perform_post_hoc_tests(
        self,
        variant_samples: List[np.ndarray],
        variant_ids: List[str],
        confidence_level: float
    ) -> Dict[str, Any]:
        """Perform post-hoc pairwise comparisons"""
        post_hoc_results = {}
        
        # Bonferroni correction
        num_comparisons = len(variant_ids) * (len(variant_ids) - 1) / 2
        adjusted_alpha = (1 - confidence_level) / num_comparisons
        
        for i in range(len(variant_ids)):
            for j in range(i + 1, len(variant_ids)):
                comparison_key = f"{variant_ids[i]}_vs_{variant_ids[j]}"
                
                try:
                    t_stat, p_value = stats.ttest_ind(
                        variant_samples[i],
                        variant_samples[j]
                    )
                    
                    post_hoc_results[comparison_key] = {
                        "t_statistic": t_stat,
                        "p_value": p_value,
                        "adjusted_p_value": p_value * num_comparisons,
                        "significant": p_value < adjusted_alpha
                    }
                    
                except Exception as e:
                    logger.error(f"Error in post-hoc test: {e}")
                    
        return post_hoc_results
