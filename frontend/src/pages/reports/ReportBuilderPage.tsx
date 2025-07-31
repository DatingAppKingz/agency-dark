import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReportBuilder from '@/components/reports/ReportBuilder';

const ReportBuilderPage: React.FC = () => {
  const { templateId } = useParams();
  const navigate = useNavigate();

  const handleSave = (savedTemplateId: string) => {
    navigate(`/dashboard/reports/view/${savedTemplateId}`);
  };

  return (
    <ReportBuilder 
      templateId={templateId} 
      onSave={handleSave}
    />
  );
};

export default ReportBuilderPage;
