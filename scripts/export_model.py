"""Export model to ONNX for optimized inference.

This script converts the trained XGBoost classifier and LightGBM regressor
to ONNX format for faster inference and broader compatibility.
"""

import argparse
import logging
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def export_to_onnx(model_path: str | Path | None = None, output_dir: str | Path | None = None):
    try:
        from onnxmltools import convert_xgboost, convert_lightgbm
        from onnxmltools.convert.common.data_types import FloatTensorType
    except ImportError:
        logger.error("ONNX tools not installed. Run: pip install onnxmltools skl2onnx")
        return

    if model_path is None:
        model_path = settings.abs_model_dir / "stage1_prerace.joblib"
    else:
        model_path = Path(model_path)

    if not model_path.exists():
        logger.error("Model not found at %s", model_path)
        return

    if output_dir is None:
        output_dir = settings.abs_model_dir / "onnx"
    else:
        output_dir = Path(output_dir)
        
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading model from %s", model_path)
    model = joblib.load(model_path)
    
    n_features = len(model.feature_columns)
    initial_type = [('float_input', FloatTensorType([None, n_features]))]

    # Export Classifier
    if hasattr(model, 'classifier'):
        base_clf = model.classifier
        # If calibrated, we extract the base estimator
        if hasattr(base_clf, "calibrated_classifiers_"):
            base_clf = base_clf.calibrated_classifiers_[0].estimator
            
        clf_type = type(base_clf).__name__
        logger.info("Exporting Classifier (%s)...", clf_type)
        
        try:
            if "XGB" in clf_type:
                onnx_clf = convert_xgboost(base_clf, initial_types=initial_type)
            elif "LGBM" in clf_type:
                onnx_clf = convert_lightgbm(base_clf, initial_types=initial_type)
            else:
                logger.warning("ONNX export for %s not fully supported. Skipping classifier.", clf_type)
                onnx_clf = None
                
            if onnx_clf:
                clf_path = output_dir / "classifier.onnx"
                with open(clf_path, "wb") as f:
                    f.write(onnx_clf.SerializeToString())
                logger.info("Saved ONNX classifier to %s", clf_path)
        except Exception as e:
            logger.error("Failed to export classifier: %s", e)

    # Export Regressor
    if hasattr(model, 'regressor'):
        logger.info("Exporting Regressor (LightGBM)...")
        try:
            onnx_reg = convert_lightgbm(model.regressor, initial_types=initial_type)
            reg_path = output_dir / "regressor.onnx"
            with open(reg_path, "wb") as f:
                f.write(onnx_reg.SerializeToString())
            logger.info("Saved ONNX regressor to %s", reg_path)
        except Exception as e:
            logger.error("Failed to export regressor: %s", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export model to ONNX")
    parser.add_argument("--model", type=str, help="Path to joblib model", default=None)
    parser.add_argument("--outdir", type=str, help="Output directory", default=None)
    args = parser.parse_args()
    
    export_to_onnx(args.model, args.outdir)
